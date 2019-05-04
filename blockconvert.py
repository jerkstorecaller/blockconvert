import json
import os
import re

with open('tld_list.txt') as file:
    tlds = [tld for tld in file.read().lower().splitlines() if '#' not in tld]
    tld_dict = dict()
    for tld in tlds:
        try:
            tld_dict[tld[0]].append(tld[1:])
        except KeyError:
            tld_dict[tld[0]] = [tld[1:]]
    TLD_REGEX = []
    for first_letter in tld_dict:
        now = '|'.join(['(?:%s)' % i for i in tld_dict[first_letter]])
        TLD_REGEX.append('(?:%s(?:%s))' % (first_letter, now))
    TLD_REGEX = '(?:%s)' % '|'.join(TLD_REGEX)

class BlockList():
    DOMAIN_STRING = '([a-z0-9_-]+(?:[.][a-z0-9_-]+)*[.]%s)[.]?' % TLD_REGEX
    ADBLOCK_STRING = rf'(?:(?:(?:\|\|)?[.]?)|(?:(?:(?:https?)?[:])?//)?)?{DOMAIN_STRING}(?:\^)?(?:\$(?:[,]?(?:(?:popup)|(?:first\-party)|(?:third\-party))))?'
    WHITELIST_STRING = '@@' + ADBLOCK_STRING
    DOMAIN_REGEX = re.compile(DOMAIN_STRING)
    ADBLOCK_REGEX = re.compile(ADBLOCK_STRING)
    WHITELIST_REGEX = re.compile(WHITELIST_STRING)
    def __init__(self):
        self.blocked_hosts = set()
        self.whitelist = set()
    def add_file(self, path):
        with open(path) as file:
            data = file.read().lower()
        try:
            data = json.loads(data)
            if 'action_map' in data and isinstance(data['action_map'], dict):
                self.parse_privacy_badger(data)
                return
        except json.JSONDecodeError:
            pass
        self.parse_adblock(data)
        self.parse_hosts(data)
    def parse_privacy_badger(self, data):
        for i in data['action_map']:
            if self.DOMAIN_REGEX.fullmatch(i):
                if isinstance(data['action_map'][i], dict) and 'heuristicaction' in data['action_map'][i]:
                    if data['action_map'][i]['heuristicaction'] == 'block':
                        self.blocked_hosts.add(i)
                    elif data['action_map'][i]['heuristicaction'] == 'cookieblock':
                        self.whitelist.add(i)
    def parse_adblock(self, data):
        for line in data.splitlines():
            if '!' not in line:
                match = self.ADBLOCK_REGEX.fullmatch(line.lower())
                if match:
                    self.blocked_hosts.add(match.group(1).lower())
                else:
                    match = self.WHITELIST_REGEX.fullmatch(line)
                    if match:
                        self.whitelist.add(match.group(1).lower())
    def parse_hosts(self, data):
        for line in data.splitlines():
            line, *_ = line.split('#')
            try:
                host, domain = line.split()
                if host in ('0.0.0.0', '127.0.0.1', '::1'):
                    if self.DOMAIN_REGEX.fullmatch(domain):
                        self.blocked_hosts.add(domain)
            except ValueError:
                pass
    def clean(self):
        for i in self.whitelist:
            try:
                self.blocked_hosts.remove(i)
            except KeyError:
                pass
    def to_adblock(self):
        self.clean()
        return '\n'.join('||%s^' % i for i in sorted(self.blocked_hosts))
    def to_hosts(self):
        self.clean()
        return '\n'.join('0.0.0.0 ' + i for i in sorted(self.blocked_hosts))
    def to_privacy_badger(self):
        self.clean()
        base = '{"action_map":{%s},"snitch_map":{%s}, "settings_map":{}}'
        url_string = '"%s":{"userAction":"","dnt":false,"heuristicAction":"block","nextUpdateTime":0}'
        return base % (','.join(url_string % i for i in sorted(self.blocked_hosts)),
                       ','.join('"%s":["1","2","3"]' % (i) for i in sorted(self.blocked_hosts)))

def main():
    blocklist = BlockList()
    try:
        paths = [os.path.join('target', f) for f in os.listdir('target')]
        paths = [f for f in paths if os.path.isfile(f)]
    except FileNotFoundError:
        print('Target directory does not exist')
        return
    paths.sort()
    for path in paths:
        blocklist.add_file(path)
    blocklist.clean()
    print('Generated %s rules' % len(blocklist.blocked_hosts))
    try:
        os.makedirs('output')
    except FileExistsError:
        pass
    with open('output/PrivacyBadger.json', 'w') as file:
        file.write(blocklist.to_privacy_badger())
    with open('output/adblock.txt', 'w') as file:
        file.write(blocklist.to_adblock())
    with open('output/hosts.txt', 'w') as file:
        file.write(blocklist.to_hosts())

if __name__ == '__main__':
    main()
