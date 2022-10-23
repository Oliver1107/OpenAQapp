"""OpenAQ Air Quality Dashboard with Flask."""
from flask import Flask, render_template, request
from aqapp.openaq import OpenAQ
from flask_sqlalchemy import SQLAlchemy
import random
from numpy import sqrt


def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
    DB = SQLAlchemy(app)
    api = OpenAQ()

    def get_results(city='Los Angeles', country=None):
        if country:
            _, body = api.measurements(
                city=city, country=country, parameter='pm25'
            )
        else:
            _, body = api.measurements(city=city, parameter='pm25')
        data = []
        for result in body['results']:
            date = result['date']['utc']
            value = result['value']
            data.append((date, value))
        return data

    class Location(DB.Model):
        id = DB.Column(DB.Integer, primary_key=True)
        country = DB.Column(DB.String, nullable=False)
        city = DB.Column(DB.String, nullable=False)

        def __repr__(self):
            return f"({self.country}, {self.city})"

    class Record(DB.Model):
        id = DB.Column(DB.Integer, primary_key=True)
        datetime = DB.Column(DB.String)
        value = DB.Column(DB.Float, nullable=False)
        location_id = DB.Column(DB.Integer, DB.ForeignKey('location.id'))
        location = DB.relationship(
            'Location', backref=DB.backref('records', lazy=True)
        )

        def __repr__(self):
            return f"(Date: {self.datetime}, Value: {self.value})"

    @app.route('/', methods=['POST', 'GET'])
    def root(country='CL', city='Los Angeles', value=18):
        """Base view."""
        try:
            place = request.values['place']
            place = place.split('/')
            country = place[0]
            city = place[1]
        except:
            country = country
            city = city
        try:
            value = request.values['value']
            if value == '':
                value = 0
            value = float(value)
        except:
            value = value
        try:
            place = Location.query.filter(
                (Location.city == city) & (Location.country == country)
            ).all()
        except:
            return render_template('load.html')
        place = place[0]
        data = []
        for rec in place.records:
            try:
                if rec.value >= value:
                    data.append(rec)
            except TypeError:
                message = "Threshold must be a number."
                return render_template('error.html', message=message)

        recs = [record for record in place.records]
        if len(recs) > 0:
            average = sum([rec.value for rec in recs]) / len(recs)
            res = []
            for x in recs:
                res.append((x.value - average) ** 2)
            sums = sum(res)
            std = sqrt(sums / (len(recs) - 1))
        else:
            average = '*No data*'
            std = '*No data*'

        country_avgs = []
        for city in Location.query.filter(Location.country == country).all():
            if len(city.records) > 0:
                city_avg = sum(
                    [rec.value for rec in city.records]) / len(city.records)
                country_avgs.append(city_avg)
        if len(country_avgs) > 0:
            country_avg = sum(country_avgs) / len(country_avgs)
            res = []
            for x in country_avgs:
                res.append((x - country_avg) ** 2)
            sums = sum(res)
            country_std = sqrt(sums / (len(country_avgs) - 1))
        else:
            country_avg = '*No data*'
            country_std = '*No data*'

        # predict_next =
        # threshold_equal_good =
        # ds_stats_trends =
        # scatter_plot =

        return render_template(
            'base.html', city=place.city, country=place.country,
            data=data, value=value, Location=Location, average=average,
            country_avg=country_avg, std=std, country_std=country_std
        )

    @app.route('/refresh')
    def refresh():
        """Pull fresh data from Open AQ and replace existing data."""
        DB.drop_all()
        DB.create_all()
        _, cities = api.cities(limit=3000)
        res = random.sample(cities['results'], k=98)
        for i in range(len(res)):
            if res[i]['city'] != 'Los Angeles':
                location = Location(
                    country=res[i]['country'],
                    city=res[i]['city']
                )
                DB.session.add(location)
                records = get_results(
                    city=res[i]['city'], country=res[i]['country']
                )
                for rec in records:
                    record = Record(
                        datetime=str(rec[0]),
                        value=rec[1],
                        location_id=(i+1),
                        location=location
                    )
                    DB.session.add(record)
        _, la = api.cities(city='Los Angeles')
        res = la['results']
        for i in range(len(res)):
            location = Location(
                country=res[i]['country'],
                city=res[i]['city']
            )
            DB.session.add(location)
            records = get_results(country=res[i]['country'])
            for rec in records:
                record = Record(
                    datetime=str(rec[0]),
                    value=rec[1],
                    location_id=(i+99),
                    location=location
                )
                DB.session.add(record)
        DB.session.commit()
        return render_template('refresh.html')

    @app.route('/cities')
    def cities():
        """View a list of cities that are in the database."""
        countries = []
        places = Location.query.all()
        for city in places:
            countries.append(city.country)
        countries = set(countries)
        return render_template(
            'cities.html', countries=countries, Location=Location
        )

    @app.route('/<country>-<city>')
    def records(country, city):
        """View the records of a certain city."""
        place = Location.query.filter(
            (Location.country == country) & (Location.city == city)
        ).all()
        result = place[0].records
        return render_template(
            'records.html', country=country, city=city, records=result
        )

    return app
