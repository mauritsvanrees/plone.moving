from zope.component import getMultiAdapter
import os


def import_step(context):
    portal = context.getSite()
    # TODO: does this work when uploading a tarball as import archive?
    # Also: that suggests a way to support uploading a tarball,
    # although perhaps not a zip.  But that part may be easy.
    if not context.isDirectory("plone.moving"):
        return
    view = getMultiAdapter((portal, portal.REQUEST), name="plone-content-import")
    directory = os.path.join(context._profile_path, "plone.moving")
    return view(directory)
