from datetime import datetime

import re
import bzrlib.branch
import bzrlib.errors
from bzrlib.diff import show_diff_trees

class Branch(object):
    def __init__(self, url):
        try:
            self.branch = bzrlib.branch.Branch.open(url)
        except bzrlib.errors.NotBranchError:
            self.branch = None

    def __bool__(self):
        return bool(getattr(self, 'branch', False))

    @property
    def history(self):
        prev_id = None
        for rev_id in self.branch.revision_history():
            yield Revision(self.branch, rev_id, prev_id)
            prev_id = rev_id

class Revision(object):
    def __init__(self, branch, rev_id, prev_id):
        self.branch = branch
        self.rev_id = rev_id
        self.prev_id = prev_id
        self._revtree = None
        self._prev_revtree = None

        self._diffstat_run = False
        self._additions = 0
        self._deletions = 0

    @property
    def revtree(self):
        if not self._revtree:
            self._revtree = self.branch.repository.revision_tree(self.rev_id)
        return self._revtree

    @property
    def prev_revtree(self):
        if not self._prev_revtree:
            self._prev_revtree = self.branch.repository.revision_tree(self.prev_id)
        return self._prev_revtree

    @property
    def id(self):
        return self.rev_id

    @property
    def no(self):
        return self.branch.revision_id_to_revno(self.rev_id)

    @property
    def timestamp(self):
        rev = self.branch.repository.get_revision(self.id)
        return datetime.utcfromtimestamp(rev.timestamp+rev.timezone)

    @property
    def author(self):
        rev = self.branch.repository.get_revision(self.id)
        return rev.get_apparent_author()

    @property
    def files(self):
        for file in self.revtree.list_files():
            file_name = file[0]
            file_id = file[3]

            yield File(self.revtree, file_name, file_id)

    @property
    def additions(self):
        if not self._diffstat_run:
            self._diffstat()

        return self._additions

    @property
    def deletions(self):
        if not self._diffstat_run:
            self._diffstat()

        return self._deletions

    def _diffstat(self):
        s = DiffStat()
        show_diff_trees(self.prev_revtree, self.revtree, s)

        self._additions = s.additions
        self._deletions = s.deletions
        self._diffstat_run = True

class File(object):
    def __init__(self, revtree, file_name, file_id):
        self.name = file_name
        self.lines = 0
        self.words = 0
        self.chars = 0

        self.revtree = revtree
        self.file_id = file_id

        self.count()

    @property
    def bytes(self):
        return self.revtree.get_file_size(self.file_id) or 0

    def count(self):
        for line in self.get_lines():
            if not line.strip():
                continue

            self.lines += 1
            self.words += len(line.split())
            self.chars += len(line)

    def get_lines(self):
        self.revtree.lock_read()
        try:
            lines = self.revtree.get_file_lines(self.file_id)
        finally:
            self.revtree.unlock()

        return lines

class DiffStat:
    addition_re = re.compile(r'^\+[^+]')
    deletion_re = re.compile(r'^\-[^-]')

    def __init__(self):
        self.additions = 0
        self.deletions = 0

    def write(self, diff_string):
        for line in diff_string.split('\n'):
            if re.search(self.addition_re, line):
                self.additions += 1
            elif re.search(self.deletion_re, line):
                self.deletions += 1

        print diff_string
