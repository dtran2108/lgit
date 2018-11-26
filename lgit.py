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
        logname_byte = logname_str
        fd = open('.lgit/config', 'w')
        fd.write(logname_byte)
        fd.close()
        fd = open('.lgit/index', 'w')
        fd.close()

        # bonus
        os.mkdir('.lgit/refs')
        os.mkdir('.lgit/refs/heads')
        fd = open('.lgit/HEAD', 'w')
        fd.write('ref: refs/heads/master')
        fd.close()
        # end bonus

    else:
        print('Git repository already initialized.')


def get_hash(filename):
    # get content and sha1 value of file
    fd = open(filename, 'r')
    try:
        content = fd.read().encode()
    except UnicodeError:
        return None, None
    return content.decode(), hashlib.sha1(content).hexdigest()


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
        tim = datetime.datetime.fromtimestamp(os.stat(name).st_mtime)
        tstamp = tim.strftime("%Y%m%d%H%M%S")

        # create a file which store content in SHA1 value of current file
        dir_name = '.lgit/objects/%s/' % hash_value[:2]
        if not os.path.exists(dir_name):
            os.mkdir(dir_name)
        fd = open(dir_name + hash_value[2:], 'w')
        fd.write(content)
        fd.close()

        # update file index
        file_index = open('.lgit/index', 'r')
        index_content = file_index.readlines()
        file_index.close()
        flag = 1
        fd = os.open('.lgit/index', os.O_WRONLY)
        os.lseek(fd, 0, 0)
        for line in index_content:
            if line[138:-1] == name:
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

    # get index's content
    file_index = open('.lgit/index', 'r')
    lines = file_index.readlines()
    file_index.close()

    if lines:
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

        # update file index
        fd = os.open('.lgit/index', os.O_WRONLY)
        os.lseek(fd, 0, 0)
        for line in lines:
            hash_value = line[56:96]
            name = line[138:]
            snapshot = open('.lgit/snapshots/%s' % ms_timestamp, 'a+')
            snapshot.write(hash_value + ' ' + name)
            snapshot.close()
            os.lseek(fd, 97, 1)
            os.write(fd, hash_value.encode())
            os.lseek(fd, len(line)-137, 1)
        os.close(fd)

        # bonus
        f = open('.lgit/HEAD', 'r')
        content = f.read()
        f.close()
        if 'master' in content:
            fd = open('.lgit/refs/heads/master', 'w')
            fd.write(ms_timestamp)
            fd.close()
        else:
            curbranch = content.strip('\n').split('/')[-1]
            fd = open('.lgit/refs/heads/%s' % curbranch, 'w')
            fd.write(ms_timestamp)
            fd.close()
        # end bonus
    else:  # if commit without ever have added yet, show the untracked files
        lgit_status()


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


def lgit_status():
    print_status()

    # get index's content
    file = open('.lgit/index', 'r')
    lines = file.readlines()
    file.close()

    # filenames = get_files('.')
    filenames = os.listdir(".")
    untracked_files = []
    to_be_committed = []
    not_staged_for_commit = []

    for name in filenames:
        if not os.path.isfile(name):
            untracked_files.append(name + '/')
            continue

        # check index file
        fd = os.open('.lgit/index', os.O_WRONLY)
        os.lseek(fd, 0, 0)
        content, hash_value = get_hash(name)
        tim = datetime.datetime.fromtimestamp(os.stat(name).st_mtime)
        tstamp = tim.strftime("%Y%m%d%H%M%S")

        # find the line contain info of current file
        curline = None
        for line in lines:
            if line[138:-1] == name:
                curline = '%s %s %s' % (tstamp, hash_value, line[56:])
                break
            else:
                os.lseek(fd, len(line), 1)
        if curline:
            # check if field3 != field2: append -> not_staged_for_commit
            if curline[56:96] != curline[15:55]:
                not_staged_for_commit.append(name)
            # check if field4 != field3: append -> to_be_committed
            elif curline[97:137] != curline[56:96]:
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


def lgit_ls_file(curpath):
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


def lgit_config_author(author):
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
    for tim in timestamp:
        f = open('.lgit/commits/%s' % tim, 'r')
        lines = f.readlines()
        # line[1]: timestamp of the commit file
        t_stamp = str(lines[1])
        year = t_stamp[:4]
        month = t_stamp[4:6]
        day = t_stamp[6:8]
        hour = t_stamp[8:10]
        minu = t_stamp[10:12]
        sec = t_stamp[12:14]
        weekday = calendar.weekday(int(year), int(month), int(day))
        print('commit ' + tim)
        print('Author: ' + lines[0].strip('\n'))
        print('Date: {} {} {} {}:{}:{} {} \n'.format(weekdays[weekday],
                                                     months[month], day,
                                                     hour, minu, sec, year))
        print('\t' + lines[3] + '\n')
        f.close()


def update_index():
    # get index's content
    file = open('.lgit/index', 'r')
    lines = file.readlines()
    file.close()

    # update index file
    fd = os.open('.lgit/index', os.O_WRONLY)
    os.lseek(fd, 0, 0)
    for line in lines:
        name = line[138:-1]
        content, hash_value = get_hash(name)
        tim = datetime.datetime.fromtimestamp(os.stat(name).st_mtime)
        tstamp = tim.strftime("%Y%m%d%H%M%S")
        os.write(fd, bytes(tstamp + ' ' + hash_value, 'utf-8'))
        os.lseek(fd, len(line) - 55, 1)
    os.close(fd)


def print_errors_checkout(errors):
    print('error: Your local changes to the following '
          'files would be overwritten by checkout:')
    for e in errors:
        print('\t' + e)
    print('Please, commit your changes or stash them '
          'before you can switch branches.')
    print('Aborting')


def lgit_checkout(branch_name):
    branch_list = os.listdir('.lgit/refs/heads')
    if branch_list:
        if branch_name in branch_list:
            # get current branch name
            head_file = open('.lgit/HEAD', 'r')
            head_content = head_file.read()
            head_file.close()
            cur_branch = head_content.strip('\n').split('/')[-1]

            if branch_name == cur_branch:
                print('Already on \'%s\'' % branch_name)
            else:
                # get the last commit of branch name
                last_commit = open('.lgit/refs/heads/%s' % branch_name, 'r')\
                    .readline().strip('\n')
                # if it is the same as current branch, \
                #   nothing has change with working files
                if last_commit != open('.lgit/refs/heads/%s' % cur_branch,
                                       'r').readline().strip('\n'):
                    # check index's content
                    index_file = open('.lgit/index', 'r')
                    index_content = index_file.readlines()
                    index_file.close()

                    # if there is any file has change without commit
                    errors = []
                    for line in index_content:
                        file_name = line[138:-1]
                        cur_hash = line[15:55]
                        commit_hash = line[97:137]
                        if cur_hash != commit_hash:
                            errors.append(file_name)
                    if errors:  # print list of changed files
                        print_errors_checkout(errors)
                        exit()

                    # change current branch
                    else:
                        # remove all files in index_file
                        for line in index_content:
                            file_name = line[138:-1]
                            os.remove(file_name)
                            # if there is any empty directory, remove it
                            try:
                                while '/' in file_name:
                                    file_name = '/'.join(file_name.
                                                         split('/')[:-1])
                                    os.rmdir(file_name)
                                os.rmdir(file_name)
                            except OSError:
                                pass

                        # rewrite index file and create new working files
                        new_index_content = ''
                        snap_file = open('.lgit/snapshots/%s'
                                         % last_commit, 'r')
                        new_files = snap_file.readlines()
                        for line in new_files:
                            new_content = open('.lgit/objects/%s/%s' % (
                                line[:2], line[2:40]), 'r').read()
                            new_name = line[41:-1]

                            # create new working file
                            try:
                                if '/' in new_name:
                                    dirs_to_create = new_name.split('/')[:-1]
                                    for i in range(len(dirs_to_create)-1):
                                        os.mkdir('/'.join
                                                 (dirs_to_create[:i+1]))
                            except FileExistsError:
                                pass
                            new_file = open(new_name, 'w+')
                            new_file.write(new_content)
                            mtime = os.stat(new_name).st_mtime
                            tim = datetime.datetime.fromtimestamp(mtime)
                            new_timestamp = tim.strftime("%Y%m%d%H%M%S")
                            new_file.close()
                            new_index_content += (new_timestamp +
                                                  (' ' + line[:40]) * 3 + ' ' +
                                                  new_name + '\n')
                        open('.lgit/index', 'w').write(new_index_content)

                # change content of file HEAD
                head_file = open('.lgit/HEAD', 'w')
                head_file.write('ref: refs/heads/%s' % branch_name)
                head_file.close()
                print('Switched to branch \'%s\'' % branch_name)
        else:  # if branch name doesn't exist
            exit('error: pathspec \'%s\' did not match'
                 'any file(s) known to git.' % branch_name)
    else:  # if call checkout without ever have commited yet
        exit('fatal: You are on a branch yet to be born')


def lgit_branch(args):
    if len(args) == 3:
        # if call branch without ever have commited yet
        if len(os.listdir('.lgit/refs/heads')) == 0:
            exit('fatal: Not a valid object name: \'master\'.')

        branch_name = args[-1]
        # if branch name exists
        if os.path.exists('.lgit/refs/heads/' + branch_name):
            exit('fatal: A branch named \'%s\' already exists.' % branch_name)

        # create new branch
        snapshots = os.listdir('.lgit/snapshots')
        fd = open('.lgit/refs/heads/%s' % branch_name, 'w')
        if snapshots:
            fd.write(max(snapshots))
        fd.close()

    elif len(args) < 3:  # if branch is called without parameters
        head_file = open('.lgit/HEAD', 'r')
        head_content = head_file.read()
        head_file.close()
        heads_files = os.listdir('.lgit/refs/heads')
        # print list branches
        for file in heads_files:
            if file == head_content.strip('\n').split('/')[-1]:
                print('* ' + file)
            else:
                print('  ' + file)


def lgit_stash():
    '''Saved working directory and index state WIP on master: b0f7304 acb
    HEAD is now at b0f7304 acb'''

    # get index's content
    file_index = open('.lgit/index', 'r')
    lines = file_index.readlines()
    file_index.close()

    # get timestamp
    tim = datetime.datetime.fromtimestamp(time.time())
    ms_timestamp = tim.strftime("%Y%m%d%H%M%S.%f")

    # get current branch name
    head_file = open('.lgit/HEAD', 'r')
    head_content = head_file.read()
    head_file.close()
    cur_branch = head_content.strip('\n').split('/')[-1]

    # get the last commit of current branch
    last_commit = open('.lgit/refs/heads/%s' % cur_branch, 'r') \
        .readline().strip('\n')

    # create a snapshot contain current working flies' info
    for line in lines:
        hash_value = line[56:96]
        name = line[138:]
        snapshot = open('.lgit/snapshots/%s' % ms_timestamp, 'a+')
        snapshot.write(hash_value + ' ' + name)
        snapshot.close()

    # create a file contains stashes
    ms = open('.lgit/commits/%s' % last_commit, 'r').readlines()[3].strip('\n')
    stashes = open('.lgit/stashes', 'a+')
    stashes.write('%s %s %s %s' % (ms_timestamp, cur_branch,
                                   last_commit[:7], ms))
    stashes.close()

    print('Saved working directory and index state WIP on %s: %s %s'
          % (cur_branch, last_commit[:7], ms))
    print('HEAD is now at %s %s' % (last_commit[:7], ms))

    # # create file COMMIT_EDITMSG
    # commit_msg = open('.lgit/commits/%s' % last_commit, 'r').readlines()[3]
    # commit_editmsg = open('.lgit/COMMIT_EDITMSG', 'w')
    # commit_editmsg.write(commit_msg)
    # commit_editmsg.close()
    #
    # # create file ORIG_HEAD
    # orig_head = open('.lgit/COMMIT_EDITMSG', 'w')
    # orig_head.write(last_commit)
    # orig_head.close()

    # remove all files in index_file
    for line in lines:
        file_name = line[138:-1]
        os.remove(file_name)
        # if there is any empty directory, remove it
        try:
            while '/' in file_name:
                file_name = '/'.join(file_name.
                                     split('/')[:-1])
                os.rmdir(file_name)
            os.rmdir(file_name)
        except OSError:
            pass

    # rewrite index file and create new working files
    new_index_content = ''
    snap_file = open('.lgit/snapshots/%s' % last_commit, 'r')
    new_files = snap_file.readlines()
    for line in new_files:
        new_content = open('.lgit/objects/%s/%s' % (
            line[:2], line[2:40]), 'r').read()
        new_name = line[41:-1]

        # create new working file
        try:
            if '/' in new_name:
                dirs_to_create = new_name.split('/')[:-1]
                for i in range(len(dirs_to_create)-1):
                    os.mkdir('/'.join
                             (dirs_to_create[:i+1]))
        except FileExistsError:
            pass
        new_file = open(new_name, 'w+')
        new_file.write(new_content)
        mtime = os.stat(new_name).st_mtime
        tim = datetime.datetime.fromtimestamp(mtime)
        new_timestamp = tim.strftime("%Y%m%d%H%M%S")
        new_file.close()
        new_index_content += (new_timestamp +
                              (' ' + line[:40]) * 3 + ' ' +
                              new_name + '\n')
    open('.lgit/index', 'w').write(new_index_content)


def lgit_stash_list():
    '''stash@{0}: WIP on master: b0f7304 acb'''

    # open file stashes
    stashes = open('.lgit/stashes', 'r')
    lines = stashes.readlines()
    stashes.close()

    # print stashes
    for line in lines:
        info = line.split()
        print('stash@{%s}: WIP on %s: %s %s'
              % (info[0], info[1], info[2], info[3]))


def lgit_stash_apply(stash_name):
    '''lgit_status()'''
    exit('not yet')


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
        update_index()
        if command == 'rm':
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
                lgit_commit(args[-1])
        elif command == 'status':
            lgit_status()
        elif command == 'ls-files':
            lgit_ls_file(curpath)
        elif command == 'config':
            lgit_config_author(args[-1])
        elif command == 'log':
            lgit_log()
        elif command == 'branch':
            lgit_branch(args)
        elif command == 'checkout':
            if len(args) > 2:
                lgit_checkout(args[-1])
        elif command == 'stash':
            if len(args) == 2:
                lgit_stash()
            elif len(args) > 2:
                ops = args[2]
                if ops == 'list':
                    lgit_stash_list()
                else:
                    lgit_stash_apply(args[3])


if __name__ == '__main__':
    main()
