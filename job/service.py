#!env/bin/python3
import os
import sys
import builtins
import json
import logging
import argparse

from configobj import ConfigObj
from validate import Validator

# SQLAlchemy
from bottle.ext import sqlalchemy as bottle_sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from bottle import Bottle
from bottle import request, response
import sqlalchemy

logger = logging.getLogger(__name__)

app = application = Bottle()

try:
    app.install(builtins.bottle_sqlalchemy)
except AttributeError:
    # import config
    pathname = os.path.dirname(os.path.realpath(__file__))
    configname = os.path.join(pathname, "config")
    config = ConfigObj(configname+".conf", configspec=configname+".spec", interpolation=False)
    config.validate(Validator())

    # setup logging
    logging.basicConfig(format=config["logging"]["format"],
                        level=config["logging"]["level"])
    # handle standalone service
    engine = create_engine(config["database"]["connection_string"], echo=True)
    sqla_plugin = bottle_sqlalchemy.Plugin(engine, keyword="db")
    app.install(sqla_plugin)

    sys.path.append(os.path.dirname(os.path.realpath(__file__))+'/..')


from models import Job, Interviewee, Interviewer
from models import Employee, Candidate


@app.route('/job', method=['OPTIONS', 'GET'])
def index(db):
    job = db.query(Job).all()
    return json.dumps([r.as_dict() for r in job], default=builtins.alchemyencoder)


@app.route('/job/:job_id', method=['OPTIONS', 'GET'])
def get_job(db, job_id=None):
    job = db.query(Job).filter(Job.id==job_id).first()
    return json.dumps(job.as_dict())


@app.route('/job/:job_id', method=['OPTIONS', 'PUT'])
def put_job(db, job_id=None):
    reqdata = request.json

    if request.content_type != "application/json":
        response.status = 400
        return "invalid request, expected header-content_type: application/json"

    job = db.query(Job).filter(Job.id==job_id).first()
    try:
        job.name = reqdata["name"]
        db.commit()
        return json.dumps(job.as_dict())
    except KeyError as e:
        logger.error(e)
        response.status = 400
        return
    except AssertionError as e:
        logger.error(e)
        response.status = 400
        return str(e)
    except sqlalchemy.exc.IntegrityError as e:
        logger.error(e)
        response.status = 400
        return e

    response.status = 400
    return "invalid request, could not locate Job with those details"



@app.route('/job', method=['OPTIONS', 'POST'])
def post_job(db):
    reqdata = request.json

    if request.content_type != "application/json":
        response.status = 400
        return "invalid request, expected header-content_type: application/json"

    try:
        job = Job(name=reqdata["name"])
        db.add(job)
        db.commit()
        return json.dumps(job.as_dict())
    except AssertionError as e:
        logger.error(e)
        response.status = 400
        return e
    except sqlalchemy.exc.IntegrityError as e:
        logger.error(e)
        response.status = 400
        return e

    response.status = 400
    return "invalid request, could not locate Job with those details"

@app.route('/job/schedule/:job_id/:candidate_id', method=['OPTIONS', 'GET'])
def get_attendee_availability(db, job_id, candidate_id):

    interviewers = db.query(Interviewer).filter(Interviewer.job_id==job_id).all()
    interviewee = db.query(Interviewee).filter(
                          (Interviewee.job_id==job_id) &
                          (Interviewee.candidate_id==candidate_id)
                    ).first()

    interviewee_availability = json.loads(interviewee.availability)

    # compare days of the week between candidate and interviewers
    matched_days = interviewee_availability.keys()
    for interviewer in interviewers:
        interviewer_availability = json.loads(interviewer.availability)
        matched_days = set(matched_days).intersection(interviewer_availability.keys())
        if not matched_days:
            response.status = 400
            return "no matches found for candidate and interviewers"

    # compare timeslots on matched days of the week with candidate and interviewers
    matched_timeslots = {}
    for interviewer in interviewers:
        interviewer_availability = json.loads(interviewer.availability)
        for day in matched_days:
            matched_timeslots[day] = list(set(interviewee_availability[day]).intersection(interviewer_availability[day]))
            if not matched_timeslots[day]:
                response.status = 400
                return "no matches found for candidate and interviewers"

    return json.dumps(matched_timeslots)



if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--listen", dest="listen", type=str, default="localhost", help="IP Address to listen on")
    parser.add_argument("-p", "--port", dest="port", type=int, default=8080, help="Port to listen on")
    parser.add_argument("-d", "--debug", dest="bottleDebug", action="store_true", help="Enable Bottle debug mode")
    parser.set_defaults(bottleDebug=True)
    pargs = vars(parser.parse_args())
    app.run(host=pargs["listen"], port=pargs["port"], debug=pargs["bottleDebug"], reloader=True)
