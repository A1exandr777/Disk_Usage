import argparse
import re
import os
from glob import glob
from sys import exit
from os.path import getsize
from diskUsage import sort_dirs, convert_bytes, traversal, get_size


MAX_NAME_COL = 50


def arguments_parsing():
    parser = argparse.ArgumentParser()
    parser.add_argument('base_path', type=str, help='Путь к начальному каталогу')
    parser.add_argument('-s', '--sort', type=str,
                        choices=['name', 'size', 'depth', 'none', 'modify'],
                        default='none',
                        help='Тип сортировки: name - по имени, size - по размеру, depth - по вложенности, modify - по дате')
    parser.add_argument('-d', '--depth', type=int, default=100,
                        help='Максимальная глубина обхода подкаталогов')
    parser.add_argument('-r', '--reverse', default=False, action='store_true',
                        help='Обратная сортировка')
    parser.add_argument('-n', '--noprogress', default=False, action='store_true',
                        help='Не показывать прогресс обработки')
    parser.add_argument('-t', '--top', default=-1, type=int,
                        help='Вывести только N верхних элементов')
    parser.add_argument('-b', '--block', default=100, type=int,
                        help='Вывести файлы, которые занимают VALUE процентов от общего размера')
    parser.add_argument('-e', '--ext', default=False, type=str,
                        help='Вывести файлы с указанным расширением и их суммарный размер')

    return parser.parse_args()


def strip_ansi(text: str) -> str:
    return re.sub(r'\x1B\[[0-?]*[ -/]*[@-~]', '', text)


def truncate_name(name: str, max_width: int) -> str:
    clean = strip_ansi(name)
    if len(clean) <= max_width:
        return name

    root, ext = os.path.splitext(clean)
    if ext and len(ext) < max_width - 5:
        visible = root[:max_width - len(ext) - 3] + "..." + ext
    else:
        visible = clean[:max_width - 3] + "..."
    return visible


def print_table(entries, base_path):
    total_size = get_size(base_path)
    base_entry = type('Entry', (), {})()
    base_entry.name = os.path.basename(base_path.rstrip("/\\"))
    base_entry.size = total_size
    base_entry.is_dir = True
    base_entry.indent = ""
    base_entry.time = None

    filtered_entries = [e for e in entries if e.name != base_entry.name]

    print_entry(base_entry, total_size)

    for e in filtered_entries:
        print_entry(e, total_size)


def print_entry(e, total_size):
    name = e.name
    if e.is_dir:
        name = f'\033[92m{name}\033[0m'

    visible_name = e.indent + name
    truncated = truncate_name(visible_name, MAX_NAME_COL)

    pad = MAX_NAME_COL - len(strip_ansi(truncated))
    size_str = convert_bytes(e.size)
    time_str = str(e.time).split('.')[0] if e.time else "N/A"

    percent = (e.size / total_size) * 100 if total_size else 0

    bar_length = 20
    filled_length = int(round(bar_length * percent / 100))
    bar = '#' * filled_length + '-' * (bar_length - filled_length)
    print(f"{truncated}{' ' * pad}  {size_str:>10}  {time_str}  {percent:6.2f}% [{bar}]")



if __name__ == '__main__':
    args = arguments_parsing()
    result, _ = traversal(args.base_path, args.depth)


    if args.ext:
        pattern = os.path.join(args.base_path, '**', f'*.{args.ext}')
        res_list = glob(pattern, recursive=True)

        print(*res_list, sep='\n')
        print(f'\nTotal size for .{args.ext}\n')

        total_ext_size = sum(getsize(f) for f in res_list if os.path.isfile(f))
        print(f'\033[96m{convert_bytes(total_ext_size)}\033[0m')
        exit()

    if args.top == -1:
        border = len(result)
    else:
        border = min(len(result), args.top)+1

    if args.block != 100:
        result = sort_dirs(result, 'size', False)
        total_size = sum(i.size for i in result if not i.is_dir)

        remaining_amount = (total_size * args.block) // 100
        output = []

        for i in result:
            if i.is_dir:
                continue
            output.append(i)
            remaining_amount -= i.size
            if remaining_amount <= 0:
                break

        print_table(output, args.base_path)

        used = total_size - remaining_amount
        print(f"\nRemaining files: {convert_bytes(total_size - used)}")

    else:
        if args.sort != 'none':
            result = sort_dirs(result, args.sort, args.reverse)

        print_table(result[:border], args.base_path)
