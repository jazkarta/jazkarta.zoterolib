# ============================================================================
# DEXTERITY ROBOT TESTS
# ============================================================================
#
# Run this robot test stand-alone:
#
#  $ bin/test -s jazkarta.zoterolib -t test_zotero_library.robot --all
#
# Run this robot test with robot server (which is faster):
#
# 1) Start robot server:
#
# $ bin/robot-server --reload-path src jazkarta.zoterolib.testing.JAZKARTA_ZOTEROLIB_ACCEPTANCE_TESTING
#
# 2) Run robot tests:
#
# $ bin/robot /src/jazkarta/zoterolib/tests/robot/test_zotero_library.robot
#
# See the http://docs.plone.org for further details (search for robot
# framework).
#
# ============================================================================

*** Settings *****************************************************************

Resource  plone/app/robotframework/selenium.robot
Resource  plone/app/robotframework/keywords.robot

Library  Remote  ${PLONE_URL}/RobotRemote

Test Setup  Open test browser
Test Teardown  Close all browsers


*** Test Cases ***************************************************************

Scenario: As a site administrator I can add a Zotero Library
  Given a logged-in site administrator
    and an add Zotero Library form
   When I type 'My Zotero Library' into the title field
    and I submit the form
   Then a Zotero Library with the title 'My Zotero Library' has been created

Scenario: As a site administrator I can view a Zotero Library
  Given a logged-in site administrator
    and a Zotero Library 'My Zotero Library'
   When I go to the Zotero Library view
   Then I can see the Zotero Library title 'My Zotero Library'


*** Keywords *****************************************************************

# --- Given ------------------------------------------------------------------

a logged-in site administrator
  Enable autologin as  Site Administrator

an add Zotero Library form
  Go To  ${PLONE_URL}/++add++Zotero Library

a Zotero Library 'My Zotero Library'
  Create content  type=Zotero Library  id=my-zotero_library  title=My Zotero Library

# --- WHEN -------------------------------------------------------------------

I type '${title}' into the title field
  Input Text  name=form.widgets.IBasic.title  ${title}

I submit the form
  Click Button  Save

I go to the Zotero Library view
  Go To  ${PLONE_URL}/my-zotero_library
  Wait until page contains  Site Map


# --- THEN -------------------------------------------------------------------

a Zotero Library with the title '${title}' has been created
  Wait until page contains  Site Map
  Page should contain  ${title}
  Page should contain  Item created

I can see the Zotero Library title '${title}'
  Wait until page contains  Site Map
  Page should contain  ${title}
