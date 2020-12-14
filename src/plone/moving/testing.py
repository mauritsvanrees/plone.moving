# -*- coding: utf-8 -*-
from plone.app.contenttypes.testing import PLONE_APP_CONTENTTYPES_FIXTURE
from plone.app.robotframework.testing import REMOTE_LIBRARY_BUNDLE_FIXTURE
from plone.app.testing import applyProfile
from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import PloneSandboxLayer
from plone.testing import z2

import plone.moving


class PloneMovingLayer(PloneSandboxLayer):

    defaultBases = (PLONE_APP_CONTENTTYPES_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        # Load any other ZCML that is required for your tests.
        # The z3c.autoinclude feature is disabled in the Plone fixture base
        # layer.
        import plone.restapi
        self.loadZCML(package=plone.restapi)
        self.loadZCML(package=plone.moving)

    def setUpPloneSite(self, portal):
        applyProfile(portal, 'plone.moving:default')


PLONE_MOVING_FIXTURE = PloneMovingLayer()


PLONE_MOVING_INTEGRATION_TESTING = IntegrationTesting(
    bases=(PLONE_MOVING_FIXTURE,),
    name='PloneMovingLayer:IntegrationTesting',
)


PLONE_MOVING_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(PLONE_MOVING_FIXTURE,),
    name='PloneMovingLayer:FunctionalTesting',
)


PLONE_MOVING_ACCEPTANCE_TESTING = FunctionalTesting(
    bases=(
        PLONE_MOVING_FIXTURE,
        REMOTE_LIBRARY_BUNDLE_FIXTURE,
        z2.ZSERVER_FIXTURE,
    ),
    name='PloneMovingLayer:AcceptanceTesting',
)
