"""python-native highly inefficient implementation of rsync"""
# optional system certificate trust
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

try:
    from getpass import getuser
    from pathlib import Path
    from platform import system
    from posixpath import join as posix_join, split as posix_split
    import hashlib
    import os
    import paramiko
    import re
    import shutil
    import stat
except ImportError as e:
    print(
        f'Failed to import required module: {e}\n'
        'You may need to re-execute quickstart.sh.\n'
        'See https://github.com/ajkessel/ttspod/blob/main/README.md for details.')
    exit()

# TODO: rework the debug/DBG and output logic
# probably want to just generate a string with output and return it
DBG = False


def md5(file_path):
    """Calculate MD5 hash of a file."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

# TODO: this should be refactored to perform the MD5 remotely
# otherwise it's probably not getting any speed benefit


def remote_get_md5(sftp, remote_file):
    """Calculate the MD5 hash of a remote file."""
    try:
        # Open remote file
        with sftp.file(remote_file, "rb") as f:
            hash_md5 = hashlib.md5()
            while True:
                data = f.read(4096)
                if not data:
                    break
                hash_md5.update(data)
            return hash_md5.hexdigest()
    except IOError:
        # If the file doesn't exist on the remote server, return None
        return None


def get_remote_size(sftp, remote_file):
    """Query the file size of a remote file."""
    try:
        info = sftp.stat(remote_file)
        return info.st_size
    except IOError:
        # If the file doesn't exist on the remote server, return None
        return None


def parse_location(fullpath):
    """split path into username, domain name, and filesystem path"""
    if not ':' in fullpath or (system() == 'Windows' and re.match(r'[A-Za-z]:', fullpath)):
        user = None
        domain = None
        path = fullpath
    else:
        m = re.match(
            r'(?P<user>[^@]*(?=@))?@?(?P<domain>[^:]*):(?P<path>.*)?', fullpath)
        user, domain, path = m.group('user'), m.group(
            'domain'), m.group('path')
    return user, domain, path


def remote_isdir(sftp, remote_dir):
    """check if remote path is a directory"""
    if DBG:
        print(f'Checking {remote_dir} for directory status... ', end='')
    try:
        file_attribute = sftp.stat(remote_dir)
        isdir = stat.S_ISDIR(file_attribute.st_mode)
    except Exception:  # pylint: disable=broad-except
        if DBG:
            print(f'Could not check remote dir {remote_dir}.')
        return None
    if isdir:
        if DBG:
            print(f"{remote_dir} is a directory.")
        return True
    else:
        if DBG:
            print(f"{remote_dir} is not a directory.")
        return False


def remote_mkdir(sftp, remote_dir):
    """create remote directory if it does not exist"""
    remote_dir = remote_dir.rstrip('/')
    paths = [remote_dir]
    # sftp mkdir has no -p (parent) mode, so we simulate it by creating each parent directory
    while '/' in remote_dir:
        remote_dir = re.sub(r'/[^/]*$', '', remote_dir)
        paths = [remote_dir] + paths
    try:
        for path in paths:
            if not remote_isdir(sftp, path):
                sftp.mkdir(path)
        return True
    except Exception:  # pylint: disable=broad-except
        if DBG:
            print(f'Could not mkdir {remote_dir}')
        return None


def remote_isfile(sftp, remote_file):
    """check if remote path is a file"""
    try:
        file_attribute = sftp.stat(remote_file)
        isfile = stat.S_ISREG(file_attribute.st_mode)
    except Exception:  # pylint: disable=broad-except
        if DBG:
            print(f'Could not check remote file {remote_file}')
        return None
    if isfile:
        if DBG:
            print(f"{remote_file} is a file")
        return True
    else:
        if DBG:
            print(f"{remote_file} is not a file")
        return False


def remote_get_filelist(sftp=None, remote_dir='', recursive=False):
    """get remote list of files to sync"""
    initial_list = sftp.listdir(path=remote_dir)
    file_list = []
    for file in initial_list:
        if remote_isdir(sftp, posix_join(remote_dir, file)):
            if recursive:
                if DBG:
                    print(f'adding remote {file} directory recursively')
                new_list = remote_get_filelist(sftp=sftp, remote_dir=posix_join(
                    remote_dir, file), recursive=recursive)
                new_list = [posix_join(file, i) for i in new_list]
                file_list.extend(new_list)
            elif DBG:
                print(
                    f'remote {file} is a directory and recursion is disabled, skipping')
        elif remote_isfile(sftp, posix_join(remote_dir, file)):
            file_list.extend([file])
        elif DBG:
            print(f'remote {file} not directory or file, skipping')
    return file_list


def local_get_filelist(local_dir='', recursive=False):
    """build a local list of files to sync"""
    initial_list = os.listdir(local_dir)
    file_list = []
    for file in initial_list:
        if os.path.isdir(os.path.join(local_dir, file)):
            if recursive:
                if DBG:
                    print(f'adding local {file} directory recursively')
                new_list = local_get_filelist(local_dir=os.path.join(
                    local_dir, file), recursive=recursive)
                new_list = [os.path.join(file, i) for i in new_list]
                file_list.extend(new_list)
            elif DBG:
                print(
                    f'local {file} is a directory and recursion is disabled, skipping')
        elif os.path.isfile(os.path.join(local_dir, file)):
            file_list.extend([file])
        elif DBG:
            print(f'local {file} not directory or file, skipping')
    return file_list


def sync(
    source=None,
    destination=None,
    port=22,
    username=None,
    password=None,
    keyfile=None,
    size_only=False,
    debug=False,
    dry_run=False,
    recursive=False
):
    """Sync source folder or file to destination folder."""
    global DBG  # pylint: disable=global-statement
    DBG = debug
    ssh = None
    sftp = None
    source_user, source_host, source_dir = parse_location(source)
    source_dir = source_dir.replace('\\', '/')
    destination_user, destination_host, destination_dir = parse_location(
        destination)
    if not keyfile and not password:
        key_list = ['id_rsa', 'id_ecdsa', 'id_ecdsa_sk',
                    'id_ed25519', 'id_ed25519_sk', 'id_dsa']
        for key in key_list:
            keyfile = os.path.join(Path.home(), '.ssh', key)
            if os.path.isfile(keyfile):
                break
        if not os.path.isfile(keyfile):
            keyfile = None
        elif DBG:
            print(f'Found local ssh keyfile {keyfile}')
    # Establish SSH connection
    if source_host and destination_host:
        raise ValueError("Cannot sync from remote host to remote host")
    if source_host or destination_host:
        host = source_host if source_host else destination_host
        if username:
            user = username
        elif source_host and source_user:
            user = source_user
        elif destination_host and destination_user:
            user = destination_user
        elif getuser():
            user = getuser()
        else:
            raise ValueError(
                "Remote host specified but no username provided or inferred.")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            if password:
                ssh.connect(host, port, user, password)
            elif keyfile:
                ssh.connect(host, port, user, key_filename=keyfile)
            else:
                raise ValueError(
                    "Either password or ssh key required to make connection")
        except Exception as err:
            raise ValueError(f'SSH connection failed {err}') from err
        if DBG:
            print("connection successful")
        # Open SFTP session
        sftp = ssh.open_sftp()
    else:
        if DBG:
            print("No hostname provided, local sync only.")

    files = []
    source = source.replace('\\', '/')
    source_trail = source.endswith('/')
    destination_trail = destination.endswith('/')
    file_only = False

    if source_host:                                    # remote source, local destination
        # check if source is a file or directory
        if remote_isfile(sftp, source_dir):
            file_only = True
            # extract path and filename
            source_dir, file = posix_split(source_dir)
            # add single file to queue
            files.append(file)
            # if destination ends with /, sync to that directory,
            # otherwise assume destination is filename
            if destination_trail:
                # normalize destination path for POSIX
                destination_dir = os.path.join(destination_dir, '')
        else:                                          # directory transfer
            file_only = False
            # if neither source nor destination ends with /
            # add last part of source dir to destination path
            if not source_trail and not destination_trail:
                destination_dir = os.path.join(
                    destination_dir, os.path.basename(os.path.normpath(source_dir)))
            source_dir = posix_join(source_dir, '')
            files = remote_get_filelist(
                sftp=sftp, remote_dir=source_dir, recursive=recursive)
            destination_dir = os.path.join(destination_dir, '')
        # create destination directory if:
        if not os.path.isdir(destination_dir):
            # there is a leading path in the destination directory
            if file_only and not destination_trail and destination_dir.count('/') > 1:
                parent_dir = re.sub(
                    r'/[^/]*$', '', destination_dir.rstrip('/'))
                try:
                    if not dry_run:
                        Path(parent_dir).mkdir(parents=True, exist_ok=True)
                except Exception as err:
                    raise ValueError(
                        f'Could not create destination directory {parent_dir}: {err}') from err
            # source is directory or source is file and dest ends with /
            if not file_only or (file_only and destination_trail):
                try:
                    if not dry_run:
                        Path(destination_dir).mkdir(
                            parents=True, exist_ok=True)
                except Exception as err:
                    raise ValueError(
                        f'Could not create destination directory {destination_dir}: {err}') from err
    elif destination_host:                               # local source, remote destination
        if os.path.isfile(source_dir):                   # source is file?
            file_only = True
            source_dir, file = os.path.split(
                source_dir)  # extract path and filename
            # add single file to queue
            files.append(file)
            if destination_trail:
                destination_dir = posix_join(destination_dir, '')
        elif os.path.isdir(source_dir):                # source is directory?
            if not source_trail and not destination_trail:
                destination_dir = posix_join(
                    destination_dir, os.path.basename(os.path.normpath(source_dir)))
            source_dir = os.path.join(source_dir, '')
            files = local_get_filelist(
                local_dir=source_dir, recursive=recursive)
            destination_dir = posix_join(destination_dir, '')
        else:                                          # source is neither file nor directory
            raise ValueError(f'Error checking status of source {source_dir}')
        # check if remote directory exists
        if not remote_isdir(sftp, destination_dir):
            if not file_only or (file_only and destination_trail):
                try:
                    # if not, create it
                    remote_mkdir(sftp, destination_dir)
                except Exception as err:
                    raise ValueError(
                        'Could not create remote destination directory '
                        f'{destination_dir}: {err}') from err
    else:                                                  # source and destination both local
        # source is file, not directory
        if os.path.isfile(source_dir):
            file_only = True
            source_dir, file = os.path.split(
                source_dir)   # extract path and filename
            # add single file to queue
            files.append(file)
            if destination_trail:  # if destination ends with /, assume it is a dir
                destination_dir = os.path.join(destination_dir, '')
        else:  # source is directory
            if not source_trail and not destination_trail:
                destination_dir = os.path.join(
                    destination_dir, os.path.basename(os.path.normpath(source_dir)))
            source_dir = os.path.join(source_dir, '')
            files = local_get_filelist(source_dir, recursive=recursive)
            destination_dir = os.path.join(destination_dir, '')
        if not os.path.isdir(destination_dir):
            if not file_only or (file_only and destination_trail):
                try:
                    if not dry_run:
                        Path(destination_dir).mkdir(
                            parents=True, exist_ok=True)
                except Exception as err:
                    raise ValueError(
                        'Could not create destination directory '
                        f'{destination_dir}: {err}') from err

    if DBG:
        print(
            f'source host: {source_host}\n'
            f'source: {source_dir}\n'
            f'destination host: {destination_host}\n'
            f'destination: {destination_dir}'
        )

    # Sync files
    if destination_host:  # local source to remote destination
        for filename in files:
            # local system can be Linux/Mac/Windows
            local_file = os.path.join(source_dir, filename)
            if filename.count('/'):
                local_file_path = re.sub(r'/[^/]*$', '', filename)
                if not dry_run:
                    remote_mkdir(sftp, posix_join(
                        destination_dir, local_file_path))
            if file_only and not destination_trail:
                remote_file = destination_dir
            else:
                # assume remote system supports POSIX paths
                remote_file = posix_join(destination_dir, filename)
            if os.path.isfile(local_file):
                local_check = os.path.getsize(
                    local_file) if size_only else md5(local_file)
                if DBG:
                    print(f'local {local_check}... ', end='')
                remote_check = get_remote_size(
                    sftp, remote_file) if size_only else remote_get_md5(sftp, remote_file)
                if DBG:
                    print(f'remote {remote_check}... ', end='')
                if remote_check is None:
                    if DBG:
                        print(
                            f"File {filename} does not exist on the remote server. Uploading...")
                    if not dry_run:
                        local_stat = os.stat(local_file)
                        times = (local_stat.st_atime, local_stat.st_mtime)
                        sftp.put(local_file, remote_file)
                        sftp.utime(remote_file, times)
                        sftp.chmod(remote_file, local_stat.st_mode)
                elif local_check != remote_check:
                    if DBG:
                        print(
                            f"File {filename} is different. Uploading updated version...")
                    if not dry_run:
                        local_stat = os.stat(local_file)
                        times = (local_stat.st_atime, local_stat.st_mtime)
                        sftp.put(local_file, remote_file)
                        sftp.utime(remote_file, times)
                        sftp.chmod(remote_file, local_stat.st_mode)
                else:
                    if DBG:
                        print(
                            f"File {filename} is identical. No need to upload.")
            elif DBG:
                print(f"Could not find source file {filename}.")
    elif source_host:  # remote source to local destination
        for filename in files:
            # assume remote system supports POSIX paths
            remote_file = posix_join(source_dir, filename)
            if not file_only and remote_file.count('/') > 1:
                remote_file_path = re.sub(r'^[^/]*/', '', remote_file)
                remote_file_path = re.sub(r'/[^/]*$', '', remote_file_path)
                if not dry_run:
                    Path(os.path.join(destination_dir, remote_file_path)).mkdir(
                        parents=True, exist_ok=True)
            local_file = os.path.join(
                destination_dir, filename
            ) if not file_only or destination_trail else destination_dir
            local_check = None
            if os.path.isfile(local_file):
                remote_check = get_remote_size(
                    sftp, remote_file) if size_only else remote_get_md5(sftp, remote_file)
                if DBG:
                    print(f'remote {remote_check}... ', end='')
                local_check = os.path.getsize(
                    local_file) if size_only else md5(local_file)
                if DBG:
                    print(f'local {local_check}... ', end='')
                if local_check != remote_check:
                    if DBG:
                        print(
                            f"File {filename} is different. Downloading updated version...")
                    if not dry_run:
                        remote_stat = sftp.stat(remote_file)
                        times = (remote_stat.st_atime, remote_stat.st_mtime)
                        sftp.get(remote_file, local_file)
                        os.utime(local_file, times)
                else:
                    if DBG:
                        print(
                            f"File {filename} is identical. No need to download.")
            else:
                if DBG:
                    print(
                        f"File {filename} does not exist on the local server. Downloading...")
                if not dry_run:
                    remote_stat = sftp.stat(remote_file)
                    times = (remote_stat.st_atime, remote_stat.st_mtime)
                    sftp.get(remote_file, local_file)
                    os.utime(local_file, times)
    else:  # local source to local destination
        for filename in files:
            local_file = os.path.join(source_dir, filename)
            remote_file = os.path.join(destination_dir, filename)
            local_check = None
            if os.path.isfile(local_file) and os.path.isfile(remote_file):
                local_check = os.path.getsize(
                    local_file) if size_only else md5(local_file)
                if DBG:
                    print(f'local {local_check}')
                remote_check = os.path.getsize(
                    remote_file) if size_only else md5(remote_file)
                if DBG:
                    print(f'remote {remote_check}')
                if local_check != remote_check:
                    if DBG:
                        print(
                            f"File {filename} is different. Copying updated version...")
                    try:
                        if not dry_run:
                            shutil.copy2(local_file, remote_file)
                    except Exception as err:  # pylint: disable=broad-except
                        print(f'Copy failed with error {err}')
                else:
                    if DBG:
                        print(
                            f"File {filename} is identical. No need to copy.")
            else:
                if DBG:
                    print(
                        f"File {filename} does not exist on the destination. Copying...")
                try:
                    if not dry_run:
                        remote_file_path = os.path.dirname(remote_file)
                        if not os.path.isdir(remote_file_path):
                            Path(remote_file_path).mkdir(
                                parents=True, exist_ok=True)
                        shutil.copy2(local_file, remote_file)
                except Exception as err:  # pylint: disable=broad-except
                    print(f'Copy failed with error {err}')

    if sftp and ssh:
        # Close connection
        sftp.close()
        ssh.close()
