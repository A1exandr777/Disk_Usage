import sys
from os import walk, path, stat
from datetime import datetime, timezone, timedelta
from fileData import FileData


def convert_bytes(num: float):
    units = ('B', 'KB', 'MB', 'GB', 'TB')
    for unit in units:
        if num < 1024.0:
            return f'{num:3.1f} {unit}'
        num /= 1024.0


def get_size(file_path) -> int:
    total_size = 0
    for root, dirs, files in walk(file_path):
        for file in files:
            f_path = path.join(root, file)
            if not path.islink(f_path):
                try:
                    total_size += path.getsize(f_path)
                except FileNotFoundError:
                    pass
    return total_size


def traversal(file_path, depth=-1):
    result = []
    max_len = 0
    prefix = 0

    processed_files = 0
    processed_size = 0

    total_files = sum(len(files) + len(dirs) for _, dirs, files in walk(file_path))

    if file_path != '/':
        if file_path.endswith('/'):
            file_path = file_path[:-1]
        prefix = len(file_path)

    for root, dirs, files in walk(file_path):
        level = root[prefix:].count(path.sep)
        if -1 < depth < level:
            continue

        indent = ''
        if level > 0:
            indent = ' ┃   ' * (level - 1) + ' ┣━'
        sub_indent = ' ┃   ' * level + ' ┣━'

        try:
            dir_time = datetime.fromtimestamp(stat(root).st_mtime,
                                              tz=timezone(timedelta(hours=5)))
        except (FileNotFoundError, PermissionError):
            dir_time = None

        dir_size = 0
        for f in files:
            f_path = path.join(root, f)
            try:
                dir_size += path.getsize(f_path)
            except (FileNotFoundError, PermissionError):
                pass

        file_data = FileData(path.basename(root), dir_size, level, indent, True, dir_time)
        result.append(file_data)
        max_len = max(max_len, len(file_data.name) + len(file_data.indent) + 1)

        processed_files += 1
        processed_size += dir_size

        bar_len = 40
        if total_files !=0:
            filled_len = int(bar_len * processed_files // total_files)
        else:
            print("Папка пустая")
            break
        bar = '█' * filled_len + '-' * (bar_len - filled_len)
        percent = (processed_files / total_files) * 100

        sys.stdout.write(
            f"\r[{bar}] {percent:5.1f}% | {processed_files}/{total_files} items "
            f"| {convert_bytes(processed_size)} | Current: {root[:25]}...{root[-25:]} "
        )
        sys.stdout.flush()

        for f in files:
            f_path = path.join(root, f)
            try:
                size = path.getsize(f_path)
                time_m = datetime.fromtimestamp(stat(f_path).st_mtime,
                                                tz=timezone(timedelta(hours=5)))
            except (FileNotFoundError, PermissionError):
                size = 0
                time_m = None

            file_data = FileData(f, size, level, sub_indent, False, time_m)
            result.append(file_data)
            max_len = max(max_len, len(file_data.name) + len(file_data.indent) + 1)

            processed_files += 1
            processed_size += size

            filled_len = int(bar_len * processed_files // total_files)
            bar = '█' * filled_len + '-' * (bar_len - filled_len)
            percent = (processed_files / total_files) * 100

            sys.stdout.write(
                f"\r[{bar}] {percent:5.1f}% | {processed_files}/{total_files} items "
                f"| {convert_bytes(processed_size)} | Current: {f_path[:25]}...{f_path[-25:]} "
            )
            sys.stdout.flush()

    print("\nScanning complete!")
    return result, max_len



def sort_dirs(file_list, sort_type, reverse):
    if sort_type == 'name':
        return sorted(file_list, key=lambda i: i.name.lower(), reverse=reverse)

    elif sort_type == 'depth':
        return sorted(file_list, key=lambda i: i.depth, reverse=reverse)

    elif sort_type == 'size':
        return sorted(file_list, key=lambda i: i.size, reverse=not reverse)

    elif sort_type == 'modify':
        return sorted(file_list, key=lambda i: i.time, reverse=reverse)