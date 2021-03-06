from yaml import load, SafeLoader
from xtemplate import Xtemplate
from lxml import etree
import os
import sys
import logging

Install_Directory = os.path.dirname(os.path.abspath(__file__))

class ConfigurationManager:
  def __init__(self, Preferences_File):
    self.preferences = load( open( Preferences_File ).read(), Loader=SafeLoader )
    # The users are those with an Active state
    self.users = [x for x in self.preferences['users'] if x['active']]
    self.accounts = self.preferences['library-accounts']
    self.session_conditions = set()
    # Update the XSL configuration file
    self.update_xsl_formatter_config_file("src/formatting/external_variables.xml")

    # Load users
    for user in self.users:
      user['condition_set'] = set()
      self.processRules( user, user['sending-rules'].items() )

  def __enter__(self):
      return self

  def __exit__(self, exc_type, exc_value, traceback):
      pass

  def get( self, configuration_path ):
    # convert the path to sequential dict/list reads
    path = configuration_path.split( '.' )
    # read them
    value = self.preferences
    for element in path:
      value = value[element]
    return value


  """
  Given a configuration path, uses the value as a filename and tries to
  open it. Takes into account the following variables:
   - $(install_dir): the path to the directory the program is located
  \param configuration_path A path to the configuration value in the form
                            path.to.value
  \return the absolute filename with all modifiers applied
  """
  def get_file( self, configuration_path ):
    value = self.get( configuration_path )


  """
  Given a user and a set a rules, analyse all the rules and store them in
  the user set of rules for later match with the session conditions.
  \param user the dictionary related to this user settings
  \param the set of rules to analyse and associate to the user
  """
  def processRules( self, user, rules ):
    for name, rule in rules:
      new_rules = self.rule_modeling( name, rule )
      user['condition_set'] |= new_rules


  """
  Register a condition linked to this session for matching against the user
  rules, and find out if a user a concerned about receiving a message at this
  moment.
  \param key the name of the rule
  \param value the value of the rule
  """
  def registerCondition(self, key, value ):
    # Deleting the existing entry for 'updated' entries, i.e. entries for which
    # the value parameter is exclusive. 'list-change' is currently the only one.
    if key == 'list-change' and (key, not value) in self.session_conditions:
      self.session_conditions.remove( (key, not value) )

    self.session_conditions.add( (key, value) )


  """
  Transform a formal rule (that cannot be directly compared to other rules
  to a rule that can be compared.

  For example a rule about matching remaining
  days is formalised as "<3d" which means the user must be warning if the
  book must be returned is less than 3 days. The expanded set of rules is
  then ( ('due-date', 0), ('due-date', 1), ('due-date', 2) ).
  \param name the name of the rule
  \param rule the formal expression of the rule
  \return the set of expanded exploitable rule expression
  """
  def rule_modeling(self, name, rule):
    rules = set()

    if type( rule ) is list:
      subrules = set()
      for subrule in rule:
        rules |= self.rule_modeling(name, subrule)

    elif name == 'due-date':
      if rule[0] == '=':
        rules.add( (name, int(rule[1])))
      elif rule[0] == '<':
        for i in range( 0, int(rule[1]) ):
          rules.add((name, i))
      else:
        logging.error( "Rule ({}, {}) not supported".format( name, rule ))

    else:
      rules.add((name, rule))

    return rules


  """
  Returns if a given rule (name of the rule, and the rule itself) matches any
  rule of the current execution.
  \param the name of the rule
  \param the rule expression
  \return the matching rule of the session as a list
  """
  def rule_match(self, name, rule):
    return set(self.rule_modeling(name, rule)) & self.session_conditions


  """
  Returns a list containing the user that are active for receiving reminder messages,
  and whose sending rules matches at least one rule of the current batch sending.
  \return the list of user that will receive a message during this execution
  """
  def getRecipients(self):
    recipients_list = list()
    for user in self.users:
      intersection = user['condition_set'] & self.session_conditions
      if intersection:
        recipients_list.append( (user['mail'], intersection) )
        logging.info( "Added recipient: {} <{}>".format( user['name'], user['mail'] ))
      else:
        logging.info( "Skipped recipient: {} <{}>".format( user['name'], user['mail'] ))
    return recipients_list


  def getAdmins(self):
    recipients_list = list()
    for user in self.users:
      if "admin" in user['roles']:
        logging.info( "Added admin recipient: {} <{}>".format( user['name'], user['mail'] ))
        recipients_list.append( (user['mail'], None ))
    return recipients_list


  def update_xsl_formatter_config_file(self, filepath):
    formatter = Xtemplate()
    content_root = None
    for user in self.preferences.get('library-users'):
      col = formatter.new_value( content_root, '/external-variables/owner-colour-list/col', user['colour'] )
      formatter.set_value( col, './@owner', user['name'] )
      content_root = formatter.getroot(col)
    with open( filepath, 'wb+' ) as ext_variables:
      etree.ElementTree(content_root).write(ext_variables)
