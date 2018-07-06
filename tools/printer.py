
import time
from sys import stdout
from collections import OrderedDict
from .defs import Status, Type
from tqdm import tqdm


class Printer(object):
    """@SLURMY
    Printer class for the parent JobHandler.

    * `parent` Parent JobHandler instance.
    * `verbosity` Verbosity of the printer's output.
    """
    def __init__(self, parent, verbosity = 1, bar_mode = False):
        ## Parent JobHandler
        self._parent = parent
        ## Printing verbosity
        self._verbosity = verbosity
        ## Running in manual submission mode?
        self._manual_mode = False
        ## Running in progress bar mode?
        self._bar_mode = bar_mode
        ## Time
        self._time = None
        ## Tags which are tracked (set during bars setup)
        self._tags = []

    def set_manual(self):
        """@SLURMY
        Set printer to manual mode.
        """
        self._manual_mode = True

    ##TODO: how to deal with negative increments (i.e. when jobs are retried), currently this is just ignored
    def _setup_bars(self):
        bars = OrderedDict()
        ## Add bar for all jobs
        n_jobs = len(self._parent.jobs)
        bar_format = '{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{postfix}]'
        bars['all'] = tqdm(total = n_jobs, desc = 'all', unit = 'job', bar_format = bar_format)
        ## Set tags that printer tracks (skip non-string tags)
        self._tags = [tag for tag in self._parent.jobs._tags if isinstance(tag, str)]
        for tag in self._tags:
            n_jobs_tag = len(self._parent.jobs._tags[tag])
            bars[tag] = tqdm(total = n_jobs_tag, desc = tag, unit = 'job', bar_format = bar_format)

        return bars

    def _get_updates(self):
        update_dict = OrderedDict()        
        ## Entry for all jobs
        update_dict['all'] = OrderedDict()
        for status in [Status.SUCCESS, Status.FAILED]:
            update_dict['all'][status.name] = len(self._parent.jobs._states[status])
        ## Entries for tracked tags
        for tag in self._tags:
            update_dict[tag] = OrderedDict()
            for status in [Status.SUCCESS, Status.FAILED]:
                update_dict[tag][status.name] = len(self._parent.jobs.get(tags = set([tag]), states = set([status])))

        return update_dict

    def _update_bars(self):
        ## Get updates
        updates = self._get_updates()
        ## Update bars
        for tag in updates:
            n_jobs = updates[tag][Status.SUCCESS.name] + updates[tag][Status.FAILED.name]
            n_update_jobs = n_jobs - self._bars[tag].n
            ## Update only if value is not negative
            if n_update_jobs > 0:
                self._bars[tag].update(n_update_jobs)
            ### Set postfix to number of success/failed jobs
            self._bars[tag].set_postfix(updates[tag])

    def start(self):
        """@SLURMY
        Start printer.
        """
        self._time = time.time()
        if self._bar_mode:
            ## Set up bars
            self._bars = self._setup_bars()
            ## Bring bars to up to speed
            n_all = len(self._parent.jobs._states[Status.SUCCESS])
            self._bars['all'].update(n_all)
            for tag in self._bars:
                if tag == 'all': continue
                n_tag = len(self._parent.jobs.get(tags = set([tag]), states = set([Status.SUCCESS])))
                self._bars[tag].update(n_tag)
        else:
            self._print_simple()

    def update(self):
        """@SLURMY
        Update printer output.
        """
        if self._bar_mode:
            self._update_bars()
        else:
            self._print_simple()

    def stop(self):
        """@SLURMY
        Stop printer.
        """
        ## Final update before we stop
        self.update()
        self._time = time.time() - self._time
        if self._bar_mode:
            ## Close bars
            for bar in self._bars.values():
                bar.close()
        stdout.write('\n')
        self.print_summary()

    def _print_simple(self):
        print_string = self._get_print_string()
        if self._manual_mode:
            print_string += ' - press enter to update status'
        stdout.write('\r'+print_string)
        stdout.flush()

    def _get_print_string(self):
        print_string = 'Jobs '
        if self._verbosity > 1:
            n_running = len(self._parent.jobs._states[Status.RUNNING])
            n_local = len(self._parent.jobs._local)
            n_batch = n_running - n_local
            print_string += 'running (batch/local/all): ({}/{}/{}); '.format(n_batch, n_local, n_running)
        n_success = len(self._parent.jobs._states[Status.SUCCESS])
        n_failed = len(self._parent.jobs._states[Status.FAILED])
        n_all = len(self._parent.jobs)
        print_string += '(success/fail/all): ({}/{}/{})'.format(n_success, n_failed, n_all)

        return print_string

    def _get_summary_string(self, time_spent = None):
        n_jobs = len(self._parent.jobs)
        n_local = len(self._parent.jobs._tags[Type.LOCAL])
        n_batch = n_jobs - n_local
        summary_dict = OrderedDict()
        summary_dict['all'] = {'string': 'Jobs processed ', 'batch': n_batch, 'local': n_local}
        summary_dict['success'] = {'string': '     successful ', 'batch': 0, 'local': 0}
        summary_dict['fail'] = {'string': '     failed ', 'batch': 0, 'local': 0}
        jobs_failed = ''
        for job in self._parent.jobs.values():
            status = job.get_status()
            if status == Status.SUCCESS:
                if job.type == Type.LOCAL:
                    summary_dict['success']['local'] += 1
                else:
                    summary_dict['success']['batch'] += 1
            elif status == Status.FAILED or status == Status.CANCELLED:
                jobs_failed += '{} '.format(job.name)
                if job.type == Type.LOCAL:
                    summary_dict['fail']['local'] += 1
                else:
                    summary_dict['fail']['batch'] += 1

        print_string = ''
        for key, summary_val in summary_dict.items():
            if key == 'fail' and not jobs_failed: continue
            n_batch = summary_val['batch']
            n_local = summary_val['local']
            n_all = summary_val['batch'] + summary_val['local']
            print_string += '{}(batch/local/all): ({}/{}/{})\n'.format(summary_val['string'], n_batch, n_local, n_all)
        if self._verbosity > 1 and jobs_failed:
            print_string += 'Failed jobs: {}\n'.format(jobs_failed)
        if time_spent:
            print_string += 'Time spent: {:.1f} s'.format(time_spent)

        return print_string

    def print_summary(self):
        """@SLURMY
        Print a summary of the job processing.
        """
        print_string = self._get_summary_string(self._time)
        stdout.write('\r'+print_string)
        stdout.write('\n')
