
import subprocess
import shlex
import logging
import os
from ..tools import options
from ..tools.utils import _prompt_decision
from .defs import bids

log = logging.getLogger('slurmy')


class Base:
    bid = bids['BASE']
    _script_options_identifier = ''
    _commands = []
    name = None
    log = None
    run_script = None
    run_args = None

    def __getitem__(self, key):
        return self.__dict__[key]

    def __setitem__(self, key, val):
        self.__dict__[key] = val

    def __contains__(self, key):
        return (key in self.__dict__)

    def __repr__(self):
        print_string = ''
        for key, val in self.__dict__.items():
            print_string += '{}: {}\n'.format(key, val)
        print_string = print_string.rstrip('\n')

        return print_string

    def sync(self, config):
        if config is None: return
        if not isinstance(config, self.__class__):
            log.error('({})Backend class "{}" does not match class "{}" of sync object'.format(self.name, self.__class__, config.__class__))
            return
        for key in self.__dict__.keys():
            if key.startswith('_'): continue
            log.debug('({})Synchronising option "{}"'.format(self.name, key))
            self[key] = self[key] or config[key]

    def write_script(self, script_folder, singularity_image = None):
        out_file_name = '{}/{}'.format(script_folder.rstrip('/'), self.name)
        ## If the provided run script is already existing, just copy it
        if os.path.isfile(self.run_script):
            os.system('cp {} {}'.format(self.run_script, out_file_name))
            with open(out_file_name, 'r') as in_file:
                self.run_script = in_file.read()
        ## Bash shebang required for slurm submission script, but probably fairly general (to be followed up after other backend implementations)
        if not self.run_script.startswith('#!'):
            self.run_script = '#!/bin/bash\n' + self.run_script
        ## Add singularity command, if image is provided
        if singularity_image is not None: self._add_singularity_command(singularity_image)
        ## Write run script
        with open(out_file_name, 'w') as out_file:
            out_file.write(self.run_script)
        ## Set run script path
        self.run_script = out_file_name

    def _check_commands(self):
        ## If we are in test mode, skip this sanity check
        if options.Main.test_mode:
            return
        for command in self._commands:
            if Base._check_command(command): continue
            log.error('{} command not found: "{}"'.format(self.bid, command))
            if _prompt_decision('Switch to test mode (batch submission will not work)'):
                options.Main.test_mode = True
                break
            raise Exception

    def _add_singularity_command(self, image_path):
        ## Define command with provided singularity image
        command = 'if [[ -z "$SINGULARITY_INIT" ]]\nthen\n  singularity exec {} $0 $@\n  exit $?\nfi\n'.format(image_path)
        ## Recursive function to scan script and find proper position for the command
        def add_command(tail, head = ''):
            line, tail = tail.split('\n', 1)
            line = line.strip()
            ## When line is not empty and is not commented out, command must be inserted before here in any case
            if line and not line.startswith('#'):
                return head + command + '{}\n'.format(line) + tail
            ## If tail doesn't contain the backend options identifier, command can be inserted here
            elif self._script_options_identifier and '#{}'.format(self._script_options_identifier) not in tail:
                return head + '{}\n'.format(line) + command + tail
            else:
                head += '{}\n'.format(line)
                return add_command(tail, head)
        ## Add the command
        self.run_script = add_command(self.run_script)

    @staticmethod
    def _check_command(command):
        proc = subprocess.Popen(shlex.split('which {}'.format(command)), stdout = subprocess.PIPE, stderr = subprocess.STDOUT, universal_newlines = True)
        ret_code = proc.wait()
        if ret_code != 0:
            return False

        return True

    ## Backend specific implementations
    def submit(self):
        return 0

    def cancel(self):
        return 0

    def status(self):
        return 0

    def exitcode(self):
        return 0
