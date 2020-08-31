def compare(version, v):
    result = []
    target_versions_files_md5 = get_target_version_json_content(version, v)
    custom_versions_files_md5 = get_version_json_content(version)
    file_name_md5 = get_file_name_md5(target_versions_files_md5)
    pkg_info_dict = get_pkg_info_dict()
    for custom_version_md5, data in custom_versions_files_md5.items():
