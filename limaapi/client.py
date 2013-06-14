# -*- coding: utf-8 -*-
import json
import urllib
import urllib2
import socket
import base64
from pyquery import PyQuery as pq
from errors import InvalidCredentials, NotLoggedIn

class LimaApi:
	modulenames = {
		'newest': 'Neueste Beiträge',
		'visits': 'Letzte Besucher meines Profils',
		'famous': 'Berühmt für 15 Minuten',
		'statistics': 'Meine Statistik',
		'notices': 'Notizen'
	}

	def make_base64(s):
		if s.find(':') != -1:
			return base64.b64encode(s)
		return s

	def __init__(self, apiurl):
		self.session = None
		self.apiurl = apiurl
		self.net_timeout = 30
		self.proxy = None
		self.proxytype = 'http'
		self.proxylogin = None
		self.useragent = 'PyLima 1.0'

	def call(self, action, *args, **keywords):
		data = {}
		keys = sorted(keywords.keys())
		for keyword in keys:
			data[keyword] = keywords[keyword]
		content = json.dumps(data)
		data = urllib.urlencode({ 'proc': action, 'args': content })
		try:
			socket.setdefaulttimeout(self.net_timeout)
			req = urllib2.Request(self.apiurl, data)
			if not self.proxy is None:
				req.set_proxy(self.proxy, self.proxytype if not self.proxytype is None else 'http')
			if not self.proxylogin is None:
				req.add_header('Authorization', 'Basic %s' % self.make_base64(self.proxylogin))
			req.add_header('User-Agent', self.useragent)
			f = urllib2.urlopen(req)
			return pq(f.read()).remove_namespaces()
		except urllib2.HTTPError, httperror:
			raise httperror
		#f = urllib2.urlopen(self.apiurl, data)
		#return pq(f.read()).remove_namespaces()

	def login(self, username, password):
		self.username, self.password = username, password
		result = self.call('login', username=username, password=password)
		if result.find('loggedin').text() == 'true':
			self.session = result.find('session').text()
		else:
			raise InvalidCredentials()

	def logout(self):
		if self.session is None:
			self.call('logout', sid=self.session)
		else:
			raise NotLoggedIn()

	def getBoards(self):
		if self.session is None:
			raise NotLoggedIn()
		result = self.call('getBoards', sid=self.session)
		if len(result.find('notloggedin')) != 0:
			raise NotLoggedIn()
		boards = []
		for board in result.find('board'):
			board = pq(board)
			name = pq(board.find('name')).text()
			url = pq(board.find('url')).text()
			boards.append(Bean(name=name, url=url))
		return boards

	def getHomepage(self):
		if self.session is None:
			raise NotLoggedIn()
		result = self.call('getHomepage', sid=self.session)
		modules = Bean()
		for module in pq(result.find('modules')).find('module'):
			module = pq(module).text()
			m = Bean(name=self.modulenames[module], type=module)
			if module == 'newest':
				threads = []
				for item in pq(result.find('newest')).find('thread'):
					item = pq(item)
					thread = Bean()
					flags = pq(item.find('flags'))
					thread.flags = Bean()
					thread.flags.important = True if pq(flags.find('important')).text() == 'true' else False
					thread.flags.sticky = True if pq(flags.find('fixed')).text() == 'true' else False
					thread.flags.closed = True if pq(flags.find('closed')).text() == 'true' else False
					thread.name = pq(item.find('name')).text()
					thread.url = pq(item.find('url')).text()
					thread.postid = pq(item.find('postid')).text()
					thread.date = pq(item.find('date')).text()
					thread.forum = pq(item.find('forum')).text()
					thread.forumurl = pq(item.find('forum')).attr('url')
					thread.user = pq(item.find('user')).text()
					threads.append(thread)
				m.threads = threads
			elif module == 'famous':
				famous = pq(result.find('famous'))
				user = pq(famous.find('user'))
				group = pq(famous.find('group'))
				domain = pq(famous.find('domain'))
				m.domain = Bean(
						name=pq(domain.find('name')).text(),
						owner=pq(domain.find('owner')).text()
				)
				m.group = Bean(
						name=pq(group.find('name')).text(),
						url=pq(group.find('url')).text(),
						members=pq(group.find('members')).text()
				)
				m.user = Bean(
						name=pq(user.find('name')).text(),
						role=pq(user.find('role')).text(),
						gulden=pq(user.find('gulden')).text(),
						stars=Bean(
							count=pq(user.find('stars count')).text(),
							color=pq(user.find('stars color')).text()
						)
				)
			setattr(modules, module, m);
		return modules

class Bean:
	def __init__(self, *args, **keywords):
		keys = sorted(keywords.keys())
		for keyword in keys:
			setattr(self, keyword,keywords[keyword])

	def __repr__(self):
		return "%s(%r)" % (self.__class__, self.__dict__)
