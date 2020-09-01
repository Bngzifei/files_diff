# coding:utf-8
import os
import sys
import time
import difflib

import pandas

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from file_diff_cmp import DEFAULT_IGNORES, FileCompDiff


class FileComparer:

    def __init__(self):
        pass

    def get_all_dirs_name(self, path):
        """获取指定路径下的子目录名,返回列表"""
        for dir_path, dir_names, filenames in os.walk(path):
            return dir_names

    def read_file(self, filename):
        """读取文件，并处理"""
        try:
            with open(filename, "r", encoding="utf-8") as fp:
                text = fp.read().splitlines()
            return text
        except (IOError, UnicodeDecodeError) as e:
            print(f"Read file error: {e}")
            # 使用数字进行标识,便于后续的退出判定
            return 2

    def write_file(self, path, filename, pkg_name1, pkg_name2):
        """写入文件,生成对比报告"""
        timestamp = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())
        version_no_html = "-".join([path, "HTML"])
        if not os.path.exists(version_no_html):
            os.mkdir(version_no_html)

        title = "{pkg_name1}-diff-to-{pkg_name2}-{timestamp}.html".format(
            pkg_name1=pkg_name1, pkg_name2=pkg_name2, timestamp=timestamp)
        comp_report_title = "/".join([version_no_html, title])
        with open(comp_report_title, "w", encoding="utf-8") as fp:
            fp.write("<meta charset='UTF-8'>")
            fp.write(filename)
            fp_path = os.path.abspath(str(fp.name))
            # 存储位置
            print("The file on {}".format(fp_path))

    def comp_file_content_diff(self, path, file1, file2, pkg_name1, pkg_name2):
        """比较两个文件内容的差异:二进制文件无法进行下面的html报告生成"""
        tf1 = self.read_file(file1)
        tf2 = self.read_file(file2)
        tf1_case = bool(tf1 == 2)
        tf2_case = bool(tf2 == 2)
        if any([tf1_case, tf2_case]):
            return 3

        # 创建一个实例 HtmlDiff
        d = difflib.HtmlDiff()
        # 生成一个比较后的报告文件，格式为html
        filename = d.make_file(tf1, tf2)
        self.write_file(path, filename, pkg_name1, pkg_name2)

    def save_diff_ret_html(self, path, path1, path2, pkg_name1, pkg_name2):
        """比较两个pkg:冲突检测,最后生成冲突文件的html格式报告"""

        # version文件不进行比较
        DEFAULT_IGNORES.append("version")
        diff_obj = FileCompDiff(path1, path2, ignore=DEFAULT_IGNORES)
        diff_infos = diff_obj.rec_report_full_closure()
        if diff_infos:
            for diff_info in diff_infos:
                dir_path = [k for k in diff_info.keys()][0]
                pathA = dir_path.split(" Diff-To ")[0]
                pathB = dir_path.split(" Diff-To ")[1]

                file_paths = [v for v in diff_info.values()][0]
                for file_path in file_paths:
                    fileA = "/".join([pathA, file_path])
                    fileB = "/".join([pathB, file_path])
                    # 二进制文件无法进行下面的html报告生成
                    self.comp_file_content_diff(path, fileA, fileB,
                                                pkg_name1, pkg_name2)
                    time.sleep(1)

    def save_diff_xlsx_report(self, path, path1, path2, pkg_name1, pkg_name2):
        """比较两个pkg:冲突检测,最后生成冲突文件的html格式报告"""
        # version文件不进行比较
        DEFAULT_IGNORES.append("version")
        diff_obj = FileCompDiff(path1, path2, ignore=DEFAULT_IGNORES)
        diff_infos = diff_obj.rec_report_full_closure()
        infos = list()
        if diff_infos:
            for diff_info in diff_infos:
                dir_path = [k for k in diff_info.keys()][0]
                pathA = dir_path.split(" Diff-To ")[0]
                pathB = dir_path.split(" Diff-To ")[1]

                file_paths = [v for v in diff_info.values()][0]
                for file_path in file_paths:
                    fileA = "/".join([pathA, file_path])
                    fileB = "/".join([pathB, file_path])
                    info = {
                        "A": "5.8.5-5.9.0-security",
                        "B": "custom-vpc-999018091801",
                        "冲突文件": file_path,
                        "A冲突文件位置": fileA,
                        "B冲突文件位置": fileB,
                    }
                    infos.append(info)

        pd_obj = pandas.DataFrame(infos)
        pd_obj.to_excel("A与B文件差异表.xlsx", index=None)
def main():
    comparer = FileComparer()
    path = os.path.join(os.getcwd(), "doc")
    path1 = r"D:\git_pro\files_diff\A"
    path2 = r"D:\git_pro\files_diff\B"
    pkg_name1 = "A"
    pkg_name2 = "B"
    comparer.save_diff_xlsx_report(path, path1, path2, pkg_name1, pkg_name2)


if __name__ == '__main__':
    main()
