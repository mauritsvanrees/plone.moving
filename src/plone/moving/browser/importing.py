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


class FullImportView(BrowserView):
    """Do a full import"""

    def __call__(self):
        return "TODO"
