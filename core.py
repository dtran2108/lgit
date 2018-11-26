#!/usr/bin/env python3
import sys
import os
import hashlib
import time
import datetime
import calendar

'''
lgit init:            initialises version control in the current
                      directory (until this has
                      been done, any lgit command should return a fatal error)
lgit add:             stages changes, should work with files and recursively
                      with directories
lgit rm:              removes a file from the working directory and the index
lgit config --author: sets a user for authoring the commits
lgit commit -m:       creates a commit with the changes currently
                      staged (if the config file is empty,
                      this should not be possible!)
lgit status:          updates the index with the content of the working
                      directory and displays the status of
                      tracked/untracked files
lgit ls-files:        lists all the files currently tracked in the index,
                      relative to the current directory
lgit log:             shows the commit history
'''


def lgit_init():
    lst = ['commits', 'objects', 'snapshots']
    if not os.path.exists('.lgit'):
        os.mkdir('.lgit')
        # create directories listed in lst
        for i in range(len(lst)):
            os.mkdir('.lgit/' + lst[i])
        logname_str = os.getenv('LOGNAME')
        logname_byte = str.encode(logname_str)
        fd = os.open('.lgit/config', os.O_CREAT | os.O_WRONLY)
        os.write(fd, logname_byte)
        os.close(fd)
        fd = os.open('.lgit/index', os.O_CREAT)
        os.close(fd)
    else:
        print('Git repository already initialized.')


def get_hash(filename):
    # get content and sha1 value of file
    fd = os.open(filename, os.O_RDONLY)
    content = os.read(fd, os.stat(filename).st_size)
    return content, hashlib.sha1(content).hexdigest()


def get_files(dir_name):
    # get all files from dir_name
    result = []
    scan = os.scandir(dir_name)
    subs = []
    for elem in scan:
        subs.append(elem.name)
    for sub in subs:
        if dir_name != '.':
            path = dir_name + '/' + sub
        else:
            path = sub
        if os.path.isfile(path):
            result.append(path)
        else:
            result += get_files(path)
    return result


def lgit_add(filenames):

    # get all files from inputs
    names = []
    if '.' in filenames or '*' in filenames:
        names = get_files('.')
    else:
        for name in filenames:
            if os.path.isfile(name):
                names.append(name)
            else:
                names += get_files(name)

    for name in names:
        content, hash_value = get_hash(name)
        tim = datetime.datetime.fromtimestamp(time.time())
        tstamp = tim.strftime("%Y%m%d%H%M%S")

        # create a file which store content in SHA1 value of current file
        dir_name = '.lgit/objects/%s/' % hash_value[:2]
        if not os.path.exists(dir_name):
            os.mkdir(dir_name)
        fd = os.open(dir_name + hash_value[2:], os.O_CREAT | os.O_WRONLY)
        os.write(fd, content)
        os.close(fd)

        # update file index
        file_index = open('.lgit/index', 'r')
        index_content = file_index.readlines()
        file_index.close()
        flag = 1
        fd = os.open('.lgit/index', os.O_WRONLY)
        os.lseek(fd, 0, 0)
        for line in index_content:
            if line[138:] == name + '\n':
                # update timestamp
                os.write(fd, bytes(tstamp, 'utf-8'))
                os.lseek(fd, 42, 1)
                # update hash value in field3
                os.write(fd, hash_value.encode())
                flag = 0
                break
            else:
                os.lseek(fd, len(line), 1)
        if flag:
            # if file has never been added
            empty_hash = ' ' * 40
            os.write(fd, bytes('%s %s %s %s %s\n' % (tstamp, hash_value,
                                                     hash_value, empty_hash,
                                                     name), 'utf-8'))
        os.close(fd)


# remove index content of the file
def rm_index(filename):
    file = open('.lgit/index', 'r')
    contents = file.readlines()
    i = 0
    flag = 0
    while i < len(contents):
        if contents[i].endswith(filename + '\n'):
            contents.pop(i)
            flag = 1
        i += 1
    file.close()
    content = ''.join(contents)
    f = open('.lgit/index', 'w')
    f.write(content)
    f.close()
    return flag


def lgit_rm(filenames):
    for filename in filenames:
        if os.path.isdir(filename):
            print('fatal: not removing \'%s\' recursively' % filename)
            exit()
        if os.path.exists(filename):
            content, hash_value = get_hash(filename)
            dir = hash_value[:2]
            file = hash_value[2:]
            flag = rm_index(filename)
            # if filename exist in index file
            if flag:
                os.remove(filename)
            else:
                print('fatal: pathspec \'%s\' did not match any files'
                      % filename)
        else:
            print('fatal: pathspec \'%s\' did not match any files' % filename)


def lgit_commit(message):

    # get timestamp
    tim = datetime.datetime.fromtimestamp(time.time())
    ms_timestamp = tim.strftime("%Y%m%d%H%M%S.%f")
    tstamp = tim.strftime("%Y%m%d%H%M%S")

    # create file in commits dir
    commit = open('.lgit/commits/%s' % ms_timestamp, 'w+')
    f = open('.lgit/config', 'r')
    # get logname from file config
    logname = f.read().strip('\n')
    f.close()
    commit.write('%s\n%s\n\n%s\n\n' % (logname, tstamp, message))
    commit.close()

    # get index's content
    file_index = open('.lgit/index', 'r')
    lines = file_index.readlines()
    file_index.close()

    # update file index
    fd = os.open('.lgit/index', os.O_WRONLY)
    os.lseek(fd, 0, 0)
    for line in lines:
        hash = line[56:96]
        name = line[138:]
        snapshot = open('.lgit/snapshots/%s' % ms_timestamp, 'a+')
        snapshot.write(hash + ' ' + name)
        snapshot.close()
        os.lseek(fd, 97, 1)
        os.write(fd, hash.encode())
        os.lseek(fd, len(line)-137, 1)
    os.close(fd)


def lgit_status():
    print_status()

    # get index's content
    file = open('.lgit/index', 'r')
    lines = file.readlines()
    file.close()

    filenames = get_files('.')
    untracked_files = []
    to_be_committed = []
    not_staged_for_commit = []

    for name in filenames:

        # update index file
        fd = os.open('.lgit/index', os.O_WRONLY)
        os.lseek(fd, 0, 0)
        content, hash_value = get_hash(name)
        tim = datetime.datetime.fromtimestamp(time.time())
        tstamp = tim.strftime("%Y%m%d%H%M%S")

        # find the line contain info of current file
        curline = None
        for line in lines:
            if line[138:] == name + '\n':
                curline = '%s %s %s' % (tstamp, hash_value, line[56:])
                os.write(fd, bytes(tstamp + ' ' + hash_value, 'utf-8'))
                break
            else:
                os.lseek(fd, len(line), 1)
        if curline:
            # check if field3 != field2: append -> not_staged_for_commit
            if curline[56:96] != curline[15:55]:
                not_staged_for_commit.append(name)
            # check if field4 != field3: append -> to_be_committed
            if curline[97:137] != curline[56:96]:
                to_be_committed.append(name)
        else:
            untracked_files.append(name)
        os.close(fd)
    if to_be_committed:
        print_to_be_committed(to_be_committed)
    if not_staged_for_commit:
        print_not_staged_for_commit(not_staged_for_commit)
    if untracked_files:
        print_untrackeds(untracked_files)


def print_status():
    print('On branch master')
    # if commit has never been called, print "No commits yet"
    if len(os.listdir('.lgit/commits')) == 0:
        print('\nNo commits yet\n')


def print_untrackeds(files):
    print('Untracked files:')
    print('  (use "./lgit.py add <file>..." to '
          'include in what will be committed)')
    print('\n\t%s\n' % '\n\t'.join(files))
    print('nothing added to commit but untracked files '
          'present (use "./lgit.py add" to track)')


def print_to_be_committed(files):
    print('Changes to be committed:')
    print('  (use "./lgit.py reset HEAD ..." to unstage)')
    print('\n\t modified: %s\n' % '\n\t modified: '.join(files))


def print_not_staged_for_commit(files):
    print('Changes not staged for commit:')
    print('  (use "./lgit.py add ..." to update what will be committed)')
    print('  (use "./lgit.py checkout -- ..." to '
          'discard changes in working directory)')
    print('\n\t modified: %s\n' % '\n\t modified: '.join(files))


def lgit_lsFile(curpath):
    f = open('.lgit/index', 'r')
    content = f.read()
    elements = content.split('\n')
    filenames = []
    for i in elements:
        temp = i.split(' ')
        filenames.append(temp[-1])
    filenames.sort()
    for filename in filenames:
        if curpath == '':
            if filename != '':
                print(filename)
        # in case lgit is called from inner dir, cut dir-name
        elif curpath in filename:
            temp = filename.split(curpath)
            print(temp[-1])


def lgit_configAuthor(author):
    f = open('.lgit/config', 'w')
    f.write(author + '\n')
    f.close()


def lgit_log():
    months = {'01': 'Jan', '02': 'Feb', '03': 'Mar', '04': 'Apr',
              '05': 'May', '06': 'June', '07': 'Jul', '08': 'Aug',
              '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dec'}
    weekdays = {0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri',
                5: 'Sat', 6: 'Sun'}
    # get files from directory .lgit/commits
    timestamp = os.listdir('.lgit/commits')
    timestamp.sort(reverse=True)
    # traverse through files in directory .lgit/commits
    for time in timestamp:
        f = open('.lgit/commits/%s' % time, 'r')
        lines = f.readlines()
        # line[1]: timestamp of the commit file
        t_stamp = str(lines[1])
        year = t_stamp[:4]
        month = t_stamp[4:6]
        day = t_stamp[6:8]
        hour = t_stamp[8:10]
        min = t_stamp[10:12]
        sec = t_stamp[12:14]
        weekday = calendar.weekday(int(year), int(month), int(day))
        print('commit ' + time)
        print('Author: ' + lines[0].strip('\n'))
        print('Date: {} {} {} {}:{}:{} {} \n'.format(weekdays[weekday],
                                                     months[month], day,
                                                     hour, min, sec, year))
        print('\t' + lines[3] + '\n')
        f.close()


def main():
    args = sys.argv

    # in case lgit.py is called from inner dir
    call = args[0]
    curpath = os.getcwd() + '/'
    # check args[0] if it has '../' or '../../' etc
    ch = call[:-7]
    if ch != '':
        # changes the current directory to the dir which has .lgit dir
        os.chdir(ch)
    mainpath = os.getcwd() + '/'
    # save the current dir if necessary
    curpath = ''.join(curpath.split(mainpath))

    # get options
    command = args[1]
    if command == 'init':
        lgit_init()
    else:
        # If there is not a .lgit dir, lgit.py will exit with a fatal error.
        if not os.path.exists('.lgit'):
            print('fatal: not a git repository ('
                  'or any of the parent directories)')
            exit()
        elif command == 'rm':
            temp = args[2:]
            filenames = []
            for name in temp:
                filenames.append(curpath + name)
            lgit_rm(filenames)
        elif command == 'add':
            temp = args[2:]
            filenames = []
            if '.' in temp and curpath != '':
                scan = os.scandir(curpath)
                for e in scan:
                    filenames.append(curpath + e.name)
            else:
                for name in temp:
                    filenames.append(curpath + name)
            lgit_add(filenames)
        elif command == 'commit':
            if '-m' not in args:
                print('Please enter a commit message with -m')
                exit()
            else:
                message = args[-1]
                lgit_commit(message)
        elif command == 'status':
            lgit_status()
        elif command == 'ls-files':
            lgit_lsFile(curpath)
        elif command == 'config':
            author = args[-1]
            lgit_configAuthor(author)
        elif command == 'log':
            lgit_log()


if __name__ == '__main__':
    main()
