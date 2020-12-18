from zope.component import getMultiAdapter
import os


def import_step(context):
    portal = context.getSite()
    if not context.isDirectory("plone.moving"):
        return
    view = getMultiAdapter((portal, portal.REQUEST), name="plone-content-import")
    directory = os.path.join(context._profile_path, "plone.moving")
    return view(directory)
