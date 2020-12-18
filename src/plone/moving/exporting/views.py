from .. import config
from Products.CMFCore.utils import getToolByName
from Products.Five import BrowserView
from plone.restapi.interfaces import ISerializeToJson
from zope.component import getAdapters
from zope.component import getMultiAdapter
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
    directory = config.DIR

    def __call__(self, directory=None, delete=True):
        self.count = 0
        if directory is None:
            self.directory = config.DIR
        else:
            self.directory = directory
        if delete:
            # For the moment, always create a fresh export.
            # Later we can think about updating.
            shutil.rmtree(self.directory)
        self.intids = queryUtility(IIntIds)
        # Note: if we would allow calling this on non-site root,
        # we should export the current item as well.
        # Maybe with Plone 6 this will work on a dexterity site root.
        # Otherwise it is probably not interesting or it is dangerous.
        # I have not tried.
        # for item in self.context.contentValues():
        #     self.export_item(item)
        self.export_item(self.context)
        # TODO: we might need to create a central meta.json with info like:
        # what is the url of the source Plone site.
        # Then we can use that when looking for a path for content urls.
        meta = self.get_central_meta()
        self._write_json(self.directory, "meta", meta)
        return "Exported {} items".format(self.count)

    def export_item(self, item):
        serializers = getAdapters((item, self.request), ISerializeToJson)
        # XXX Do not call this when making a GS export, as it does not work.
        item_dir = self._make_dir()
        # write meta.json
        meta = self.get_meta(item)
        self._write_json(item_dir, "meta", meta)
        for name, serializer in serializers:
            content = serializer()
            if not content:
                continue
            if not name:
                # Note: all content will have the same "@id":
                # "http://localhost:8080/Plone/@@plone-export",
                # so we might pop it.  But needs check.
                # Also skip @components, items, next_item, previous_item.
                # We might use is_folderish for a check.
                name = "default"
                # self._handle_blobs
                # Special handling for blobs
                for key, value in content.items():
                    if isinstance(value, dict) and "filename" in value:
                        # TODO this may not work for Archetypes.
                        field = getattr(item, key)
                        # blob_path = field._blob.committed()
                        _filename, ext = os.path.splitext(value["filename"])
                        self._write_bytes(item_dir, key + ext, field.data)
            self._write_json(item_dir, name, content)
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

    def get_central_meta(self):
        # Gather info for central meta.json.
        if self.context.portal_type == "Plone Site":
            portal = self.context
        else:
            # We could use plone.api, but if we ever want this in core,
            # plone.api should not be used.
            portal = getMultiAdapter(
                (self.context, self.request), name="plone_portal_state"
            ).portal()
        info = {
            "source_url": self.context.absolute_url(),
            "source_path": "/".join(self.context.getPhysicalPath()),
            "source_portal_url": portal.absolute_url(),
            "source_portal_path": "/".join(portal.getPhysicalPath()),
            # Maybe add date.
        }
        return info

    def _make_dir(self):
        # create dir/0/0, dir/0/999, dir/1/1000, etc.
        new_dir_name = os.path.join(self.directory, str(self.count // config.ITEMS_PER_DIR), str(self.count))
        if not os.path.isdir(new_dir_name):
            os.makedirs(new_dir_name, mode=0o700)
        return new_dir_name

    def _write_json(self, item_dir, name, content):
        # TODO When using GS export step, we should be calling
        # setup_context.writeDataFile instead.
        filename = os.path.join(item_dir, name + ".json")
        with open(filename, "w") as myfile:
            myfile.write(json.dumps(content))
        logger.info("Wrote %s", filename)

    def _write_bytes(self, item_dir, name, content):
        filename = os.path.join(item_dir, name)
        with open(filename, "wb") as myfile:
            myfile.write(content)
        logger.info("Wrote %s", filename)
