from .. import config
from Acquisition import aq_base
from Acquisition.interfaces import IAcquirer
from Products.CMFCore.utils import getToolByName
from Products.Five import BrowserView
from plone.restapi.interfaces import IDeserializeFromJson
from plone.restapi.services.locking.locking import is_locked
from zope.cachedescriptors.property import Lazy
from zope.component import getAdapters
from zope.component import getMultiAdapter
from zope.interface import alsoProvides
from plone.restapi.services.content.utils import add
from plone.restapi.services.content.utils import create
from Products.CMFPlone.utils import safe_hasattr
# from zExceptions import BadRequest
# from zExceptions import Unauthorized
from zope.component import queryMultiAdapter
from zope.event import notify
from zope.lifecycleevent import ObjectCreatedEvent

import json
import logging
import os
import plone.protect.interfaces
import pkg_resources
import six


try:
    pkg_resources.get_distribution("plone.app.multilingual")
    PAM_INSTALLED = True
except pkg_resources.DistributionNotFound:
    PAM_INSTALLED = False


logger = logging.getLogger(__name__)


class ContentImportView(BrowserView):
    """Do an import of content"""
    count = 0
    source_url = ""
    source_path = ""
    source_portal_url = ""
    source_portal_path = ""

    def __call__(self):
        self.count = 0
        # Disable CSRF protection to avoid the confirmation dialog.
        # TODO: use POST request from form with protection.
        if "IDisableCSRFProtection" in dir(plone.protect.interfaces):
            alsoProvides(self.request, plone.protect.interfaces.IDisableCSRFProtection)
        self.read_central_meta_json()
        self.catalog = getToolByName(self.context, "portal_catalog")
        # Note: if the dir does not exist or is no dir, os.walk gives an empty list.
        for dirpath, dirnames, filenames in os.walk(config.DIR):
            if "default.json" in filenames:
                imported = self.import_item(dirpath, *filenames)
                if imported:
                    self.count += 1
        return "Imported {} items".format(self.count)

    @Lazy
    def portal(self):
        if self.context.portal_type == "Plone Site":
            # For the moment this is the only option, but let's be careful.
            return self.context
        # We could use plone.api, but if we ever want this in core,
        # plone.api should not be used.
        return getMultiAdapter(
            (self.context, self.request), name="plone_portal_state"
        ).portal()

    def read_central_meta_json(self):
        filepath = os.path.join(config.DIR, "meta.json")
        if not os.path.exists(filepath):
            return
        logger.info("Reading %s", filepath)
        with open(filepath) as myfile:
            content = json.loads(myfile.read())
        self.source_url = content.get("source_url", "")
        self.source_path = content.get("source_path", "")
        self.source_portal_url = content.get("source_portal_url", "")
        self.source_portal_path = content.get("source_portal_path", "")

    def import_item(self, dirpath, *filenames):
        __traceback_info__ = dirpath
        logger.info("Importing item at %s", dirpath)
        all_info = {}
        blobs = {}
        for name in filenames:
            filepath = os.path.join(dirpath, name)
            key, ext = os.path.splitext(name)
            if ext != ".json":
                logger.info("Found non json file, will use as blob, at %s", filepath)
                blobs[key] = filepath
                continue
            logger.info("Reading %s", filepath)
            with open(filepath) as myfile:
                content = json.loads(myfile.read())
            all_info[key] = content

        # Get meta info.  We might also get some of this from default.json.
        # Maybe we need less in meta.
        meta = all_info["meta"]
        # if "front-page" in meta.get("path", ""):
        #     import pdb; pdb.set_trace()
        # See if the object already exists.
        obj = self.get_object(**meta)
        if obj is None:
            # We need to get some parent, either from default["parent"] or meta.
            path = meta["path"]
            parent_path = path.rpartition("/")[0]
            parent_obj = self.get_object(path=parent_path)
            if parent_obj is None:
                logger.warning("Parent object not found, cannot create content for %s", path)
                return
            default = all_info["default"]
            # Code taken from plone.restapi add.py FolderPost.reply.
            # It would be nice if we could call that method directly, but it does too much.
            # We would need to split it a bit, especially:
            # don't get json from the request body, and don't change the response.
            type_ = default.get("@type", None)
            id_ = default.get("id", None)
            title = default.get("title", None)
            translation_of = default.get("translation_of", None)
            language = default.get("language", None)
            # except Unauthorized / BadRequest
            obj = create(parent_obj, type_, id_=id_, title=title)
            # Acquisition wrap temporarily to satisfy things like vocabularies
            # depending on tools
            temporarily_wrapped = False
            if IAcquirer.providedBy(obj) and not safe_hasattr(obj, "aq_base"):
                obj = obj.__of__(self.context)
                temporarily_wrapped = True
            deserializer = queryMultiAdapter((obj, self.request), IDeserializeFromJson)
            if deserializer is None:
                logger.error("Cannot deserialize type %s", obj.portal_type)
                return
            if blobs:
                for fieldname, path in blobs.items():
                    if fieldname in default:
                        with open(path, "rb") as myfile:
                            default[fieldname]["data"] = myfile.read()

            # except DeserializationError as e:
            deserializer(validate_all=True, data=default, create=True)
            if temporarily_wrapped:
                obj = aq_base(obj)
            if not getattr(deserializer, "notifies_create", False):
                notify(ObjectCreatedEvent(obj))
            obj = add(parent_obj, obj, rename=not bool(id_))
            obj_path = "/".join(obj.getPhysicalPath())
            logger.info("Created %s at %s", type_, obj_path)

            # Link translation given the translation_of property
            if PAM_INSTALLED:
                # Note: untested.
                from plone.app.multilingual.interfaces import (
                    IPloneAppMultilingualInstalled,
                )  # noqa
                from plone.app.multilingual.interfaces import ITranslationManager

                if (
                    IPloneAppMultilingualInstalled.providedBy(self.request)
                    and translation_of
                    and language
                ):
                    source = self.get_object(translation_of)
                    if source:
                        manager = ITranslationManager(source)
                        manager.register_translation(language, obj)

            # TODO: call other, named deserializers, but they do not work currently anyway.
        else:
            obj_path = "/".join(obj.getPhysicalPath())
            if is_locked(obj, self.request):
                # TODO: We could throw an error, but we should probably just unlock.
                logger.warning("Content is locked: %s", obj_path)
            logger.info("Updating existing content at %s", obj_path)
            deserializers = getAdapters((obj, self.request), IDeserializeFromJson)
            if not deserializers:
                logger.error("Cannot deserialize type %s", obj.portal_type)
                return
            for name, deserializer in deserializers:
                if not name:
                    name = "default"
                # XXX This traceback info overrides the previous.
                # When done in a separate method, it should be fine.
                # __traceback_info__ = name
                __traceback_info__ = dirpath, name
                content = all_info[name]
                if name == "local_roles":
                    # TODO Fix this in plone.restapi.
                    logger.info("Ignoring local_roles deserializer for now, as it does not accept a content parameter.")
                    continue
                if name == "default" and blobs:
                    for fieldname, path in blobs.items():
                        if fieldname in content:
                            with open(path, "rb") as myfile:
                                content[fieldname]["data"] = myfile.read()
                try:
                    deserializer(data=content)
                except TypeError:
                    # Happens for site root.  But I want to fix it there too, if that is acceptable.
                    logger.info("TypeError, likely because deserializer does not accept data keyword argument: %s", deserializer)
            # TODO: maybe try / except DeserializationError

        # Report back that we made an import.
        return True

    def get_object(self, **kwargs):
        # Adapted from plone/restapi/services/content/add.py
        if kwargs.get("portal_type", "") == "Plone Site":
            return self.portal
        uid = kwargs.get("uid")
        if uid:
            brain = self.catalog(UID=uid)
            if brain:
                return brain[0].getObject()
            # We can debate whether we should try by path when the uid is not found.
            # If not, we should return here.
            # Maybe quit or complain when uid and path are both given and they do not match,
            # because I foresee problems.
        path = kwargs.get("path")
        if not path:
            return
        if six.PY2:
            path = path.encode("utf8")
        if path.startswith("/"):
            # Resolve by path
            if self.source_portal_path:
                if path.startswith(self.source_portal_path):
                    path = path.replace(self.source_portal_path, "/".join(self.portal.getPhysicalPath()), 1)
            path = path.lstrip("/")
        elif path.startswith(self.source_portal_url):
            # Resolve by URL
            path = path[len(self.source_portal_url) + 1 :]
        elif path.startswith(self.portal.absolute_url()):
            # Resolve by URL
            path = path[len(self.portal.absolute_url()) + 1 :]
        else:
            logger.error("Ignoring unknown path %r", path)
            return
        obj = self.portal.restrictedTraverse(path, None)
        if obj is None:
            return
        # Importing /Plone/front-page to /Plone2/front-page should work.
        # But when I try this with two Plone Sites in the same database,
        # it finds the item in the original Plone site, thanks to Acquisition...
        # So check if this object is within the current Plone Site.
        # Check should not be needed now that we pass source_portal_path,
        # But I want to make sure.
        obj_path = obj.getPhysicalPath()
        portal_path = self.portal.getPhysicalPath()
        if len(obj_path) < len(portal_path):
            # Path to Zope object???
            return
        for section in range(len(portal_path)):
            if portal_path[section] != obj_path[section]:
                # Object is in a different portal.
                return
        return obj
