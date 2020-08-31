# coding:utf-8
import os
import stat
from itertools import filterfalse

__all__ = ['clear_cache', 'cmp', 'cmpfiles', 'DEFAULT_IGNORES']

_cache = {}
BUFSIZE = 8 * 1024

DEFAULT_IGNORES = ['RCS', 'CVS', 'tags', '.git', '.svn', '.hg', '.bzr',
                   '_darcs', '__pycache__']


def clear_cache():
    """Clear the filecmp cache."""
    _cache.clear()


def cmp(f1, f2, shallow=True):
    """Compare two files.

    Arguments:

    f1 -- First file name

    f2 -- Second file name

    shallow -- Just check stat signature (do not read the files).
               defaults to True.

    Return value:

    True if the files are the same, False otherwise.

    This function uses a cache for past comparisons and the results,
    with cache entries invalidated if their stat information
    changes.  The cache may be cleared by calling clear_cache().

    """

    s1 = _sig(os.stat(f1))
    s2 = _sig(os.stat(f2))
    if s1[0] != stat.S_IFREG or s2[0] != stat.S_IFREG:
        return False
    if shallow and s1 == s2:
        return True
    if s1[1] != s2[1]:
        return False

    outcome = _cache.get((f1, f2, s1, s2))
    if outcome is None:
        outcome = _do_cmp(f1, f2)
        if len(_cache) > 100:  # limit the maximum size of the cache
            clear_cache()
        _cache[f1, f2, s1, s2] = outcome
    return outcome


def _sig(st):
    return (stat.S_IFMT(st.st_mode),
            st.st_size,
            st.st_mtime)


def _do_cmp(f1, f2):
    bufsize = BUFSIZE
    with open(f1, 'rb') as fp1, open(f2, 'rb') as fp2:
        while True:
            b1 = fp1.read(bufsize)
            b2 = fp2.read(bufsize)
            if b1 != b2:
                return False
            if not b1:
                return True


class FileCompDiff:

    def __init__(self, a, b, ignore=None, hide=None):
        self.left = a
        self.right = b
        if hide is None:
            self.hide = [os.curdir, os.pardir]  # Names never to be shown
        else:
            self.hide = hide
        if ignore is None:
            self.ignore = DEFAULT_IGNORES
        else:
            self.ignore = ignore

    def phase0(self):
        self.left_list = _filter(os.listdir(self.left),
                                 self.hide + self.ignore)
        self.right_list = _filter(os.listdir(self.right),
                                  self.hide + self.ignore)
        self.left_list.sort()
        self.right_list.sort()

    def phase1(self):
        a = dict(zip(map(os.path.normcase, self.left_list), self.left_list))
        b = dict(zip(map(os.path.normcase, self.right_list), self.right_list))
        self.common = list(map(a.__getitem__, filter(b.__contains__, a)))
        self.left_only = list(
            map(a.__getitem__, filterfalse(b.__contains__, a)))
        self.right_only = list(
            map(b.__getitem__, filterfalse(a.__contains__, b)))

    def phase2(self):
        self.common_dirs = []
        self.common_files = []
        self.common_funny = []

        for x in self.common:
            a_path = os.path.join(self.left, x)
            b_path = os.path.join(self.right, x)

            ok = 1
            try:
                a_stat = os.stat(a_path)
            except OSError as why:
                print('Can\'t stat', a_path, ':', why.args[1])
                ok = 0
            try:
                b_stat = os.stat(b_path)
            except OSError as why:
                print('Can\'t stat', b_path, ':', why.args[1])
                ok = 0

            if ok:
                a_type = stat.S_IFMT(a_stat.st_mode)
                b_type = stat.S_IFMT(b_stat.st_mode)
                if a_type != b_type:
                    self.common_funny.append(x)
                elif stat.S_ISDIR(a_type):
                    self.common_dirs.append(x)
                elif stat.S_ISREG(a_type):
                    self.common_files.append(x)
                else:
                    self.common_funny.append(x)
            else:
                self.common_funny.append(x)

    def phase3(self):
        xx = cmpfiles(self.left, self.right, self.common_files)
        self.same_files, self.diff_files, self.funny_files = xx

    def phase4(self):
        self.subdirs = {}
        for x in self.common_dirs:
            a_x = os.path.join(self.left, x)
            b_x = os.path.join(self.right, x)
            # 保证这里添加的对象是当前类的实例
            self.subdirs[x] = FileCompDiff(a_x, b_x, self.ignore, self.hide)

    def phase4_closure(self):
        self.phase4()
        for sd in self.subdirs.values():
            sd.phase4_closure()

    def report(self):
        print('diff', self.left, self.right)
        if self.diff_files:
            self.diff_files.sort()
        print("==========>>>")
        print('Differing files :', self.diff_files)
        print("==========>>>")
        diff_info = None
        if self.diff_files:
            diff_info = {
                f"{self.left} Diff-To {self.right}": self.diff_files
            }
        return diff_info

    def rec_report_full_closure(self):
        infos = list()
        diff_info = self.report()
        if diff_info:
            # 如果有,添加至冲突列表中
            infos.append(diff_info)
        for st in self.subdirs.values():
            # 关键在于这里遍历出来的st不是当前类的对象
            # 递归执行子目录,注意返回的是一个列表
            sub_diff_info = st.rec_report_full_closure()
            if sub_diff_info:
                # 如果有,添加至冲突列表中
                infos.extend(sub_diff_info)
        return infos

    method_map = dict(subdirs=phase4,
                      same_files=phase3, diff_files=phase3, funny_files=phase3,
                      common_dirs=phase2, common_files=phase2,
                      common_funny=phase2,
                      common=phase1, left_only=phase1, right_only=phase1,
                      left_list=phase0, right_list=phase0)

    def __getattr__(self, attr):
        if attr not in self.method_map:
            raise AttributeError(attr)
        self.method_map[attr](self)
        return getattr(self, attr)


def _filter(flist, skip):
    return list(filterfalse(skip.__contains__, flist))


def cmpfiles(a, b, common, shallow=True):
    """Compare common files in two directories.

    a, b -- directory names
    common -- list of file names found in both directories
    shallow -- if true, do comparison based solely on stat() information

    Returns a tuple of three lists:
      files that compare equal
      files that are different
      filenames that aren't regular files.

    """
    res = ([], [], [])
    for x in common:
        ax = os.path.join(a, x)
        bx = os.path.join(b, x)
        res[_cmp(ax, bx, shallow)].append(x)
    return res


# Compare two files.
# Return:
#       0 for equal
#       1 for different
#       2 for funny cases (can't stat, etc.)
#
def _cmp(a, b, sh, abs=abs, cmp=cmp):
    try:
        return not abs(cmp(a, b, sh))
    except OSError:
        return 2
