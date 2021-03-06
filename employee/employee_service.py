#!env/bin/python3
import os
import sys
import builtins
import json
import logging
import argparse

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
    # setup logging
    logging.basicConfig(format=os.environ.get('SV_LOGGING_FORMAT'),
                        level=os.environ.get('SV_LOGGING_LEVEL'))
    # handle standalone service
    engine = create_engine(os.environ.get('SV_DB_CONNECTION'), echo=False)
    sqla_plugin = bottle_sqlalchemy.Plugin(engine, keyword="db")
    app.install(sqla_plugin)

    sys.path.append(os.path.dirname(os.path.realpath(__file__))+'/..')

import models
from models import Employee, Interviewer


@app.route('/employee', method=['OPTIONS', 'GET'])
def index(db):
    employees = db.query(Employee).all()
    return json.dumps([r.as_dict() for r in employees], default=models.alchemyencoder)


@app.route('/employee/:employee_id', method=['OPTIONS', 'GET'])
def get_employee(db, employee_id=None):
    employee = db.query(Employee).filter(Employee.id==employee_id).first()
    return json.dumps(employee.as_dict())


@app.route('/employee/:employee_id', method=['OPTIONS', 'PUT'])
def put_employee(db, employee_id=None):
    reqdata = request.json

    if request.content_type != "application/json":
        response.status = 400
        return "invalid request, expected header-content_type: application/json"

    employee = db.query(Employee).filter(Employee.id==employee_id).first()
    try:
        employee.name = reqdata["name"]
        employee.title = reqdata["title"]
        db.commit()
    except KeyError as e:
        logger.error(e)
        response.status = 400
        return e
    except sqlalchemy.exc.IntegrityError as e:
        logger.error(e)
        response.status = 400
        return e

    return json.dumps(employee.as_dict())


@app.route('/employee', method=['OPTIONS', 'POST'])
def post_employee(db):
    reqdata = request.json

    if request.content_type != "application/json":
        response.status = 400
        return "invalid request, expected header-content_type: application/json"

    try:
        employee = Employee(**reqdata)
        db.add(employee)
        db.commit()
    except sqlalchemy.exc.IntegrityError as e:
        logger.error(e)
        response.status = 400
        return e
    return json.dumps(employee.as_dict())


@app.route('/employee/availability', method=['OPTIONS', 'PUT'])
def put_employee_availability(db):
    reqdata = request.json

    if request.content_type != "application/json":
        response.status = 400
        return "invalid request, expected header-content_type: application/json"

    interviewer = db.query(Interviewer).filter(
        (Interviewer.job_id==reqdata["job_id"]) &
        (Interviewer.employee_id==reqdata["employee_id"])
        ).first()
    try:
        interviewer.availability=json.dumps(reqdata["availability"])
        db.commit()
        return json.dumps(interviewer.as_dict())
    except AssertionError as e:
        logger.error(e)
        response.status = 400
        return str(e)
    except sqlalchemy.exc.IntegrityError as e:
        logger.error(e)
        response.status = 400
        return e

    response.status = 400
    return "invalid request, could not locate Interviewer with those details"


@app.route('/employee/availability', method=['OPTIONS', 'POST'])
def post_employee_availability(db):
    reqdata = request.json

    if request.content_type != "application/json":
        response.status = 400
        return "invalid request, expected header-content_type: application/json"

    try:
        interviewer = Interviewer(job_id=reqdata["job_id"],
                                  employee_id=reqdata["employee_id"],
                                  availability=json.dumps(reqdata["availability"]))
        db.add(interviewer)
        db.commit()
        return json.dumps(interviewer.as_dict())
    except AssertionError as e:
        logger.error(e)
        response.status = 400
        return str(e)
    except sqlalchemy.exc.IntegrityError as e:
        logger.error(e)
        response.status = 400
        return e

    response.status = 400
    return "invalid request, could not locate Interviewer with those details"

