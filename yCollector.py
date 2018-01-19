#!/usr/bin/python

import os,sys
import shlex, subprocess
import logging
import math

from yoctopuce.yocto_api import *
from yoctopuce.yocto_humidity import *
from yoctopuce.yocto_temperature import *
from yoctopuce.yocto_pressure import *


def setup_custom_logger(name):
    formatter = logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    handler = logging.FileHandler('/tmp/yoctopuce.log', mode='a')
    handler.setFormatter(formatter)
    screen_handler = logging.StreamHandler(stream=sys.stdout)
    screen_handler.setFormatter(formatter)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.addHandler(screen_handler)
    return logger


# Helper method to calculate the dew point
# https://en.wikipedia.org/wiki/Dew_point
def dew_point(temp, hum):
    return ( ( 241.2*math.log(hum/100.0) + (4222.03716*temp)/(241.2+temp) ) / ( 17.5043 - math.log(hum/100.0) - (17.5043*temp)/(241.2+temp) ) )


def main(host='localhost', port=8086, db='mydb'):
    logger = setup_custom_logger('yoctopuce_logger')

    errmsg = YRefParam()
    # Setup the API to use local USB devices
    if YAPI.RegisterHub("http://127.0.0.1:4444") == YAPI.SUCCESS:
        logger.info("VirtualHub is on")
    else:
        logger.info("VirtualHub is off, will try direct USB mode")
        if YAPI.RegisterHub("usb", errmsg) != YAPI.SUCCESS:
            logger.error("Initialization failed. " + errmsg.value)
            sys.exit(-1)

    # Find all Yocto-Meteo modules
    modules = {}
    module = YModule.FirstModule()
    while module is not None:
        #print module.get_serialNumber()
        if module.get_serialNumber().startswith('METEOMK') and module.isOnline():
            modules[module.get_serialNumber()] = module.get_logicalName()
        module = module.nextModule()

    if len(modules.keys()) == 0:
        logger.warning("No online modules found. Closing.")
        sys.exit(-2)

    # Get sensor readings
    for target in modules.keys():
        #print modules[target]
        name = modules[target]
        humSensor = YHumidity.FindHumidity(target+'.humidity')
        pressSensor = YPressure.FindPressure(target+'.pressure')
        tempSensor = YTemperature.FindTemperature(target+'.temperature')
        #-----------------
        logger.info("Obtaining sensor readings...")
        hum = humSensor.get_currentValue()
        press = pressSensor.get_currentValue()
        temp = tempSensor.get_currentValue()
        dew = dew_point(temp, hum)

        cmd = "curl -i -XPOST 'http://%s:%i/write?db=%s' --data-binary 'yoctopuce %s=%f,%s=%f,%s=%f,%s=%f'"%(host,port,db,name+'_humidity',hum,name+'_pressure',press,name+'_temperature',temp,name+'_dewpoint',dew)
        #print cmd
        args = shlex.split(cmd)
        #print args

        proc = subprocess.Popen( args, stdout = subprocess.PIPE, stderr = subprocess.STDOUT )
        output = proc.communicate()[0]
        if proc.returncode != 0:
            logger.error(output)
            sys.exit(-3)
        else:
            logger.debug(output)

        logger.info("Sensor readings sent to the database.")

if __name__ == '__main__':
    main('elrond.irb.hr',8086,'PixelLab_sensors')
