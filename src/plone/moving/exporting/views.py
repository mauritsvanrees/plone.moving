from .. import config
from Products.CMFCore.utils import getToolByName
from Products.Five import BrowserView
from plone.restapi.interfaces import ISerializeToJson
from zope.component import getAdapters
from zope.component import queryUtility
from zope.intid.interfaces import IIntIds
from zope.intid.interfaces import IntIdMissingError

import json
import logging
import os
import shutil


logger = logging.getLogger(__name__)


class ContentExportView(BrowserView):
    """Export the content of the full site."""
    count = 0

    def __call__(self):
        self.count = 0
        # For the moment, always create a fresh export.
        # Later we can think about updating.
        shutil.rmtree(config.DIR)
        self.intids = queryUtility(IIntIds)
        # Note: if we would allow calling this on non-site root,
        # we should export the current item as well.
        # Maybe with Plone 6 this will work on a dexterity site root.
        # Otherwise it is probably not interesting or it is dangerous.
        # I have not tried.
        # for item in self.context.contentValues():
        #     self.export_item(item)
        self.export_item(self.context)
        return "Exported {} items".format(self.count)

    def export_item(self, item):
        serializers = getAdapters((item, self.request), ISerializeToJson)
        item_dir = self._make_dir()
        # write meta.json
        meta = self.get_meta(item)
        self._write(item_dir, "meta", meta)
        for name, serializer in serializers:
            if not name:
                # Note: all content will have the same "@id":
                # "http://localhost:8080/Plone/@@plone-export",
                # so we might pop it.  But needs check.
                # Also skip @components, items, next_item, previous_item.
                # We might use is_folderish for a check.
                name = "default"
            content = serializer()
            if not content:
                continue
            self._write(item_dir, name, content)
        self.count += 1
        # Check if item is folderish.
        # Note: item.contentValues can be inherited from parent,
        # but item.objectIds not.
        if not item.objectIds():
            return
        for subitem in item.contentValues():
            self.export_item(subitem)

    def get_meta(self, item):
        """Compile content for meta.json.

        Maybe call this moving.json.
        We could register this as serializer too.
        That would avoid a special case for this package,
        and serves as an example.
        """
        try:
            uid = item.UID()
        except AttributeError:
            # PloneSite has not UID, at least not in 5.2 and lower
            uid = ""
        # I am not sure yet which of these keys are really needed.
        info = {
            "UID": uid,
            "portal_type": item.portal_type,
            "path": "/".join(item.getPhysicalPath()),
        }
        if self.intids is not None:
            # Get the Intid.
            # Not sure how to force a particular intid when registering in the new site.
            # This is probably not possible.  But having the intid may be useful.
            # Look at how collective.relationhelpers rebuilds the relations:
            # get all relations, purge relations and intids utilities,
            # reregister all content with new intids, restore relations.
            # https://github.com/collective/collective.relationhelpers/blob/master/src/collective/relationhelpers/api.py#L51
            try:
                info["intid"] = self.intids.getId(item)
            except IntIdMissingError:
                # Happens for Plone Site root, and can be others.
                # We could call self.intids.register instead,
                # but that is a write, so plone.protect would ask for confirmation.
                pass
        return info

    def _make_dir(self):
        # create config.DIR/0/0, config.DIR/0/999, config.DIR/1/1000, etc.
        new_dir_name = os.path.join(config.DIR, str(self.count // config.ITEMS_PER_DIR), str(self.count))
        if not os.path.isdir(new_dir_name):
            os.makedirs(new_dir_name, mode=0o700)
        return new_dir_name

    def _write(self, item_dir, name, content):
        filename = os.path.join(item_dir, name + ".json")
        with open(filename, "w") as myfile:
            myfile.write(json.dumps(content))
        logger.info("Wrote %s", filename)
