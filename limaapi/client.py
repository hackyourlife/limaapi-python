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
		return self.rpc_call(action, data)

	def rpc_call(self, action, data):
		content = json.dumps(data)
		return self.raw_call(action, content)

	def raw_call(self, action, content):
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
			name = board.find('name').text
			url = board.find('url').text
			boards.append(Bean(name=name, url=url))
		return boards

	def getHomepage(self):
		if self.session is None:
			raise NotLoggedIn()
		result = self.call('getHomepage', sid=self.session)
		modules = Bean()
		for module in result.find('modules').find('module'):
			module = module.text
			m = Bean(name=self.modulenames[module], type=module)
			if module == 'newest':
				threads = []
				for item in result.find('newest').find('thread'):
					thread = Bean()
					flags = item.find('flags')
					thread.flags = Bean()
					thread.flags.important = True if flags.find('important').text == 'true' else False
					thread.flags.sticky = True if flags.find('fixed').text == 'true' else False
					thread.flags.closed = True if flags.find('closed').text == 'true' else False
					thread.name = item.find('name').text
					thread.url = item.find('url').text
					thread.postid = item.find('postid').text
					thread.date = item.find('date').text
					thread.forum = item.find('forum').text
					thread.forumurl = item.find('forum').get('url')
					thread.user = item.find('user').text
					threads.append(thread)
				m.threads = threads
			elif module == 'famous':
				famous = result.find('famous')
				user = famous.find('user')
				group = famous.find('group')
				domain = famous.find('domain')
				m.domain = Bean(
						name=domain.find('name').text(),
						owner=domain.find('owner').text()
				)
				m.group = Bean(
						name=group.find('name').text(),
						url=group.find('url').text(),
						members=group.find('members').text()
				)
				m.user = Bean(
						name=user.find('name').text(),
						role=user.find('role').text(),
						gulden=user.find('gulden').text(),
						stars=Bean(
							count=user.find('stars count').text(),
							color=user.find('stars color').text()
						)
				)
			setattr(modules, module, m);
		return modules

	def getPostThread(self, postid):
		if self.session is None:
			raise NotLoggedIn()
		result = self.call('getPostThread', id=postid)
		return Bean(
				location=result.find('location').text(),
				name=result.find('name').text(),
				page=result.find('page').text(),
				perpage=result.find('perpage').text()
		)

	def getThread(self, url, page=None, perpage=None):
		data = {};
		data['sid'] = self.session
		data['url'] = url
		if not page is None:
			data['page'] = page
		if not perpage is None:
			data['perpage'] = perpage
		result = self.rpc_call('getThread', data)

		posts = []
		for post in result.find('post'):
			user = post.find('user')
			userdeleted = True if user.get('deleted') == 'true' else False

			def parseXML(node):
				bean = Bean(tag=node.tag)
				if node.tag == 'text':
					if node.text is None:
						return None
					bean.text = node.text
				elif node.tag == 'goto':
					bean.type = node.get('type')
					if bean.type == 'thread':
						bean.url = node.get('url')
					else:
						bean.id = node.get('id')
				elif node.tag == 'link':
					bean.url = node.get('url')
				elif node.tag == 'img':
					bean.src = node.get('src')
					bean.alt = node.get('alt')
				elif node.tag == 'youtube':
					bean.video = node.text
				elif node.tag == 'math':
					bean.url = node.find('url').text
					bean.raw = node.find('raw').text
				elif node.tag == 'code':
					bean.display = 'inline' if node.get('display') == 'inline' else 'block'
					bean.language = node.get('language', None)

				if not node.tag in ['br', 'img', 'text', 'math']:
					bean.children = []
					for n in node.getchildren():
						x = parseXML(n)
						if not x is None:
							bean.children.append(x)
				return bean

			content = []
			for node in post.find('content'):
				x = parseXML(node)
				if not x is None:
					content.append(x)

			posts.append(Bean(
				user=Bean(
					name=user.text,
					author=True if user.get('author') == 'true' else False,
					deleted=userdeleted,
					online=True if user.get('online') == 'true' else False,
					avatar=user.get('avatar') if not userdeleted else None,
					rank=user.get('rank') if not userdeleted else None,
					gulden=user.get('gulden') if not userdeleted else None,
					role=user.get('role') if not userdeleted else None,
					starcount=user.get('starcount') if not userdeleted else None
				),
				type=post.find('type').text,
				date=post.find('date').text,
				id=post.find('id').text,
				content=content
			))

		return Bean(
				name=result.find('name').text(),
				url=url,
				pages=result.find('pages').text(),
				writable=True if result.find('writable').text() == 'true' else False,
				posts=posts
		)

class Bean:
	def __init__(self, *args, **keywords):
		keys = sorted(keywords.keys())
		for keyword in keys:
			setattr(self, keyword,keywords[keyword])

	def __repr__(self):
		return "%s(%r)" % (self.__class__, self.__dict__)
