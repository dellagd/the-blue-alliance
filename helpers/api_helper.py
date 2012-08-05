import json
import logging

from google.appengine.api import memcache
from google.appengine.ext import db

import tba_config
from helpers.event_helper import EventHelper
from helpers.match_helper import MatchHelper
from models.event import Event
from models.event_team import EventTeam
from models.match import Match
from models.team import Team

class ApiHelper(object):
    """Helper for api_controller."""
    @classmethod
    def getTeamInfo(self, team_key):
        """
        Return a Team dict with basic information.
        """
        memcache_key = "api_team_info_%s" % team_key
        team_dict = memcache.get(memcache_key)
        if team_dict is None:
            team = Team.get_by_key_name(team_key)
            if team is not None:
                team_dict = dict()
                team_dict["key"] = team.key().name()
                team_dict["team_number"] = team.team_number
                team_dict["name"] = team.name
                team_dict["nickname"] = team.nickname
                team_dict["website"] = team.website
                team_dict["event_keys"] = [a.event.key().name() for a in team.events]
                team_dict["location"] = team.address
                
                try:
                    team.do_split_address()
                    team_dict["location"] = team.split_address.get("full_address", None)
                    team_dict["locality"] = team.split_address.get("locality", None)
                    team_dict["region"] = team.split_address.get("region", None)
                    team_dict["country"] = team.split_address.get("country", None)
                except Exception, e:
                    logging.info("Failed to include Address for api_team_info_%s" % team_key)
                
                #TODO: Reduce caching time before 2013 season. 2592000 is one month -gregmarra 
                if tba_config.CONFIG["memcache"]: memcache.set(memcache_key, team_dict, 2592000)
            else:
                return None
        return team_dict
    
    
    @classmethod
    def getEventInfo(self, event_key):
        """
        Return an Event dict with basic information
        """
        
        memcache_key = "api_event_info_%s" % event_key
        event_dict = memcache.get(memcache_key)
        if event_dict is None:
            event = Event.get_by_key_name(event_key)
            if event is not None:
                event_dict = dict()
                event_dict["key"] = event.key().name()
                event_dict["year"] = event.year
                event_dict["event_code"] = event.event_short
                event_dict["name"] = event.name
                event_dict["short_name"] = event.short_name
                event_dict["location"] = event.location
                event_dict["official"] = event.official
                event_dict["facebook_eid"] = event.facebook_eid

                if event.start_date:
                    event_dict["start_date"] = event.start_date.isoformat()
                else:
                    event_dict["start_date"] = None
                if event.end_date:
                    event_dict["end_date"] = event.end_date.isoformat()
                else:
                    event_dict["end_date"] = None
                
                event_dict["teams"] = [EventTeam.team.get_value_for_datastore(event_team).name() for event_team in event.teams.fetch(500)]
                event_dict["matches"] = [a.key().name() for a in event.match_set.fetch(500)]
                
                #TODO: Reduce caching time before 2013 season. 2592000 is one month -gregmarra
                if tba_config.CONFIG["memcache"]: memcache.set(memcache_key, event_dict, 2592000)
        return event_dict
    
    
    @classmethod
    def addTeamEvents(self, team_dict, year):
        """
        Consume a Team dict, and return it with a year's Events.
        """
        memcache_key = "api_team_events_%s_%s" % (team_dict["key"], year)
        event_list = memcache.get(memcache_key)
        
        if event_list is None:
            team = Team.get_by_key_name(team_dict["key"])
            events = [a.event for a in team.events if a.year == int(year)]
            events = sorted(events, key=lambda event: event.start_date)
            event_list = [self.getEventInfo(e.key().name()) for e in events]
            for event_dict, event in zip(event_list, events):
                event_dict["team_wlt"] = EventHelper.getTeamWLT(team_dict["key"], event)

            #TODO: Reduce caching time before 2013 season. 2592000 is one month -gregmarra
            if tba_config.CONFIG["memcache"]: memcache.set(memcache_key, event_list, 2592000)
        
        team_dict["events"] = event_list
        return team_dict

    @classmethod
    def addTeamDetails(self, team_dict, year):
        """
        Consume a Team dict, and return it with a year's Events filtered and Matches added
        """
        
        # TODO Matches should live under Events - gregmarra 1 feb 2011
        # TODO Filter Events by year - gregmarra 1 feb 2011
        
        memcache_key = "api_team_details_%s_%s" % (team_dict["key"], year)
        matches_list = memcache.get(memcache_key)
        if matches_list is None:
            matches = list()
            team = Team.get_by_key_name(team_dict["key"])
            for e in [a.event for a in team.events]:
                match_list = e.match_set.filter("team_key_names =", team.key().name()).fetch(500)
                matches.extend(match_list)
            matches_list = list()
            for match in matches:
                match_dict = dict()
                match_dict["key"] = match.key().name()
                match_dict["event"] = match.event.key().name()
                match_dict["comp_level"] = match.comp_level
                match_dict["set_number"] = match.set_number
                match_dict["match_number"] = match.match_number
                match_dict["team_keys"] = match.team_key_names
                match_dict["alliances"] = json.loads(match.alliances_json)
                matches_list.append(match_dict)
            
            #TODO: Reduce caching time before 2013 season. 2592000 is one month -gregmarra
            if tba_config.CONFIG["memcache"]: memcache.set(memcache_key, matches_list, 2592000)
        
        team_dict["matches"] = matches_list
        return team_dict