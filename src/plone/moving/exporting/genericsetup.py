from zope.component import getMultiAdapter
import os


def export_step(context):
    portal = context.getSite()
    # context.writeDataFile('registry.xml', safe_encode(body), 'text/xml')
    import pdb; pdb.set_trace()
    directory = os.path.join(context._profile_path, "plone.moving")
    view = getMultiAdapter((portal, portal.REQUEST), name="plone-content-export")
    return view(directory)
