from .. import config
from Products.CMFCore.utils import getToolByName
from Products.Five import BrowserView
from plone.restapi.interfaces import IDeserializeFromJson
from zope.component import getAdapters
from zope.component import queryUtility
from zope.intid.interfaces import IIntIds
from zope.intid.interfaces import IntIdMissingError

import json
import logging
import os
import shutil


logger = logging.getLogger(__name__)


class ContentImportView(BrowserView):
    """Do an import of content"""
    count = 0

    def __call__(self):
        self.count = 0
        # Note: if the dir does not exist or is no dir, os.walk gives an empty list.
        for dirpath, dirnames, filenames in os.walk(config.DIR):
            if "default.json" in filenames:
                imported = self.import_item(dirpath, *filenames)
                if imported:
                    self.count += 1
        return "Imported {} items".format(self.count)

    def import_item(self, dirpath, *filenames):
        __traceback_info__ = dirpath
        logger.info("Importing item at %s", dirpath)
        all_info = {}
        for name in filenames:
            filepath = os.path.join(dirpath, name)
            key, ext = os.path.splitext(name)
            if ext != ".json":
                logger.warning("Ignoring non json file at %s", filepath)
                continue
            logger.info("Reading %s", filepath)
            with open(filepath) as myfile:
                content = json.loads(myfile.read())
            all_info[key] = content

        # Hey, what should the context be?
        # First determine what the parent should be?
        # deserializers = getAdapters((item, self.request), IDeserializeFromJson)

        # Report back that we made an import.
        return True
