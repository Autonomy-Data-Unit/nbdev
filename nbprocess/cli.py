# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/10_cli.ipynb.

# %% ../nbs/10_cli.ipynb 1
from __future__ import annotations
import json,warnings

from .read import *
from .sync import *
from .process import *
from .processors import *

from execnb.nbio import *
from fastcore.basics import *
from fastcore.imports import *
from fastcore.net import *
from fastcore.script import call_parse
from fastcore import shutil
from fastcore.utils import globtastic, run, repo_details
from ghapi.all import GhApi, github_auth_device

from urllib.error import HTTPError
from contextlib import redirect_stdout
import os, tarfile

# %% auto 0
__all__ = ['nbprocess_ghp_deploy', 'nbprocess_sidebar', 'FilterDefaults', 'nbprocess_filter', 'update_version', 'bump_version',
           'nbprocess_bump_version', 'extract_tgz', 'prompt_user', 'refresh_quarto_yml', 'nbprocess_new',
           'nbprocess_quarto']

# %% ../nbs/10_cli.ipynb 5
@call_parse
def nbprocess_ghp_deploy():
    "Deploy docs in doc_path from settings.ini to GitHub Pages"
    try: from ghp_import import ghp_import
    except:
        warnings.warn('Please install ghp-import with `pip install ghp-import`')
        return
    ghp_import(config_key('doc_path'), push=True, stderr=True, no_history=True)

# %% ../nbs/10_cli.ipynb 7
def _create_sidebar(
    path:str=None, symlinks:bool=False, file_glob:str='*.ipynb', file_re:str=None, folder_re:str=None, 
    skip_file_glob:str=None, skip_file_re:str=None, skip_folder_re:str='^[_.]'):
    path = config_key("nbs_path") if not path else Path(path)
    files = globtastic(path, symlinks=symlinks, file_glob=file_glob, file_re=file_re,
                       folder_re=folder_re, skip_file_glob=skip_file_glob,
                       skip_file_re=skip_file_re, skip_folder_re=skip_folder_re
                      ).sorted().map(Path)
    yml_path = path/'sidebar.yml'
    yml = "website:\n  sidebar:\n    contents:\n"
    yml += '\n'.join(f'      - {o.relative_to(path)}' for o in files)
    yml_path.write_text(yml)
    return files

# %% ../nbs/10_cli.ipynb 8
@call_parse
def nbprocess_sidebar(
    path:str=None, # path to notebooks
    symlinks:bool=False, # follow symlinks?
    file_glob:str='*.ipynb', # Only include files matching glob
    file_re:str=None, # Only include files matching regex
    folder_re:str=None, # Only enter folders matching regex
    skip_file_glob:str=None, # Skip files matching glob
    skip_file_re:str=None, # Skip files matching regex
    skip_folder_re:str='^[_.]' # Skip folders matching regex
):
    "Create sidebar.yml"
    _create_sidebar(path, symlinks, file_glob=file_glob, file_re=file_re, folder_re=folder_re,
                   skip_file_glob=skip_file_glob, skip_file_re=skip_file_re, skip_folder_re=skip_folder_re)

# %% ../nbs/10_cli.ipynb 10
class FilterDefaults:
    "Override `FilterDefaults` to change which notebook processors are used"
    def _nothing(self): return []
    xtra_procs=xtra_preprocs=xtra_postprocs=_nothing
    
    def base_preprocs(self): return [infer_frontmatter, add_show_docs, insert_warning]
    def base_postprocs(self): return []
    def base_procs(self):
        return [strip_ansi, hide_line, filter_stream_, lang_identify, rm_header_dash,
                clean_show_doc, exec_show_docs, rm_export, clean_magics, hide_, add_links]

    def procs(self):
        "Processors for export"
        return self.base_procs() + self.xtra_procs()

    def preprocs(self):
        "Preprocessors for export"
        return self.base_preprocs() + self.xtra_preprocs()

    def postprocs(self):
        "Postprocessors for export"
        return self.base_postprocs() + self.xtra_postprocs()

# %% ../nbs/10_cli.ipynb 11
@call_parse
def nbprocess_filter(
    nb_txt:str=None  # Notebook text (uses stdin if not provided)
):
    "A notebook filter for quarto"
    os.environ["IN_TEST"] = "1"
    filt = get_config().get('exporter', FilterDefaults)()
    printit = False
    if not nb_txt: nb_txt,printit = sys.stdin.read(),True
    nb = dict2nb(json.loads(nb_txt))
    with open(os.devnull, 'w') as dn:
        with redirect_stdout(dn):
            NBProcessor(nb=nb, procs=filt.procs(), preprocs=filt.preprocs(), postprocs=filt.postprocs()).process()
    res = nb2str(nb)
    del os.environ["IN_TEST"]
    if printit: print(res, flush=True)
    else: return res

# %% ../nbs/10_cli.ipynb 13
_re_version = re.compile('^__version__\s*=.*$', re.MULTILINE)

def update_version():
    "Add or update `__version__` in the main `__init__.py` of the library"
    fname = get_config().path("lib_path")/'__init__.py'
    if not fname.exists(): fname.touch()
    version = f'__version__ = "{get_config().version}"'
    with open(fname, 'r') as f: code = f.read()
    if _re_version.search(code) is None: code = version + "\n" + code
    else: code = _re_version.sub(version, code)
    with open(fname, 'w') as f: f.write(code)


def bump_version(version, part=2):
    version = version.split('.')
    version[part] = str(int(version[part]) + 1)
    for i in range(part+1, 3): version[i] = '0'
    return '.'.join(version)

@call_parse
def nbprocess_bump_version(
    part:int=2  # Part of version to bump
):
    "Increment version in `settings.py` by one"
    cfg = get_config()
    print(f'Old version: {cfg.version}')
    cfg.d['version'] = bump_version(get_config().version, part)
    cfg.save()
    update_version()
    print(f'New version: {cfg.version}')

# %% ../nbs/10_cli.ipynb 15
def extract_tgz(url, dest='.'): 
    with urlopen(url) as u: tarfile.open(mode='r:gz', fileobj=u).extractall(dest)

# %% ../nbs/10_cli.ipynb 16
def _get_info(owner, repo, default_branch='main', default_kw='nbprocess'):
    try: from ghapi.all import GhApi
    except: 
        print('Could not get information from GitHub automatically because `ghapi` is not installed. \nEdit `settings.ini` to verify all information is correct.\n')
        return (default_branch,default_kw,'')
    
    api = GhApi(owner=owner, repo=repo, token=os.getenv('GITHUB_TOKEN'))
    
    try: r = api.repos.get()
    except HTTPError:
        msg= [f"Could not access repo: {owner}/{repo} to find your default branch - `{default} assumed.\n",
              "Edit `settings.ini` if this is incorrect.\n"
              "In the future, you can allow nbprocess to see private repos by setting the environment variable GITHUB_TOKEN as described here: https://nbdev.fast.ai/cli.html#Using-nbdev_new-with-private-repos \n"]
        print(''.join(msg))
        return (default_branch,default_kw,'')
    
    return r.default_branch, default_kw if not r.topics else ' '.join(r.topics), r.description

# %% ../nbs/10_cli.ipynb 18
def prompt_user(**kwargs):
    config_vals = kwargs
    print('================ nbprocess Configuration ================\n')
    for v in config_vals:
        if not config_vals[v]:
            print('Please enter the following information:\n')
            inp = input(f'{v}: ')
            config_vals[v] = inp     
        else: print(f"{v}: '{config_vals[v]}' Automatically inferred from git.")
    print(f"\n`settings.ini` updated with configuration values.")
    return config_vals

# %% ../nbs/10_cli.ipynb 19
def _fetch_from_git(raise_err=False):
    "Get information for settings.ini from the user."
    try:
        url = run('git config --get remote.origin.url')
        owner,repo = repo_details(url)
        branch,keywords,descrip = _get_info(owner=owner, repo=repo)
        author = run('git config --get user.name').strip()
        email = run('git config --get user.email').strip()
    except Exception as e:
        if raise_err: raise(e)
        return dict(lib_name=None,user=None,branch=None,author=None,author_email=None)
    return dict(lib_name=repo.replace('-', '_'), user=owner, branch=branch, author=author, 
                author_email=email, keywords=keywords, description=descrip)

# %% ../nbs/10_cli.ipynb 21
_quarto_yml="""ipynb-filters: [nbprocess_filter]

project:
  type: website
  output-dir: {doc_path}
  preview:
    port: 3000
    browser: false

format:
  html:
    theme: cosmo
    css: styles.css
    toc: true

website:
  title: "{lib_name}"
  description: "{description}"
  execute: 
    enabled: false
  twitter-card: true
  open-graph: true
  reader-mode: true
  repo-branch: {branch}
  repo-url: {git_url}
  repo-actions: [issue]
  navbar:
    background: primary
    search: true
    left:
      - text: Home
        file: index.ipynb
    right:
      - icon: github
        href: {git_url}
  sidebar:
    style: "floating"

metadata-files: 
  - sidebar.yml
  - custom.yml

"""

def refresh_quarto_yml():
    "Generate `_quarto.yml` from `settings.ini`."
    cfg = get_config()
    p = cfg.path('nbs_path')/'_quarto.yml'
    vals = {k:cfg[k] for k in ['doc_path', 'lib_name', 'description', 'branch', 'git_url']}
    yml=_quarto_yml.format(**vals)
    p.write_text(yml)

# %% ../nbs/10_cli.ipynb 22
@call_parse
def nbprocess_new():
    "Create a new project from the current git repo"
    config = prompt_user(**_fetch_from_git())
    # download and untar template, and optionally notebooks
    tgnm = urljson('https://api.github.com/repos/fastai/nbprocess-template/releases/latest')['tag_name']
    FILES_URL = f"https://github.com/fastai/nbprocess-template/archive/{tgnm}.tar.gz"
    extract_tgz(FILES_URL)
    path = Path()
    nbexists = True if first(path.glob('*.ipynb')) else False
    for o in (path/f'nbprocess-template-{tgnm}').ls():
        if o.name == 'index.ipynb':
            new_txt = o.read_text().replace('your_lib', config['lib_name'])
            o.write_text(new_txt)
        if o.name == '00_core.ipynb':
            if not nbexists: shutil.move(str(o), './')
        elif not Path(f'./{o.name}').exists(): shutil.move(str(o), './')
    shutil.rmtree(f'nbprocess-template-{tgnm}')

    # auto-config settings.ini from git
    settings_path = Path('settings.ini')
    settings = settings_path.read_text()
    settings = settings.format(**config)
    settings_path.write_text(settings)
    refresh_quarto_yml()

# %% ../nbs/10_cli.ipynb 24
@call_parse
def nbprocess_quarto(
    path:str=None, # path to notebooks
    doc_path:str=None, # path to output docs
    symlinks:bool=False, # follow symlinks?
    file_glob:str='*.ipynb', # Only include files matching glob
    file_re:str=None, # Only include files matching regex
    folder_re:str=None, # Only enter folders matching regex
    skip_file_glob:str=None, # Skip files matching glob
    skip_file_re:str=None, # Skip files matching regex
    skip_folder_re:str='^[_.]', # Skip folders matching regex
    preview:bool=False # Preview the site instead of building it
):
    "Create quarto docs and README.md"
    cfg = get_config()
    cfg_path = cfg.config_path
    refresh_quarto_yml()
    path = config_key("nbs_path") if not path else Path(path)
    idx_path = path/'index.ipynb'
    files = _create_sidebar(path, symlinks, file_glob=file_glob, file_re=file_re, folder_re=folder_re,
                   skip_file_glob=skip_file_glob, skip_file_re=skip_file_re, skip_folder_re=skip_folder_re)
    doc_path = config_key("doc_path") if not doc_path else Path(doc_path)
    tmp_doc_path = config_key('nbs_path')/f"{cfg['doc_path']}"
    shutil.rmtree(doc_path, ignore_errors=True)
    cmd = 'preview' if preview else 'render'
    os.system(f'cd {path} && quarto {cmd} --no-execute')
    if not preview:
        if idx_path.exists(): os.system(f'cd {path} && quarto render {idx_path} -o README.md -t gfm --no-execute')

        if (tmp_doc_path/'README.md').exists():
            (cfg_path/'README.md').unlink(missing_ok=True)
            shutil.move(str(tmp_doc_path/'README.md'), cfg_path) # README.md is temporarily in the nbs/docs folder

        if tmp_doc_path.parent != cfg_path: # move docs folder to root of repo if it doesn't exist there
            shutil.rmtree(doc_path, ignore_errors=True)
            shutil.move(tmp_doc_path, cfg_path)
