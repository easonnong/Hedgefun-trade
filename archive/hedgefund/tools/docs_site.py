#!/usr/bin/env python3
"""An internal documentation site from the Markdown already in this repo: search, a sidebar, Mermaid, one place to look.

  pip install mkdocs-material mkdocs-static-i18n jieba     # once (jieba = Chinese word segmentation for search)
  tools/docs_site.py serve             # http://127.0.0.1:8000, reloads as you edit
  tools/docs_site.py build             # static site in .docs_site/site/

Nothing is written for the site: it ASSEMBLES what is already here -- docs/, the README, AUDIT.md, the emergency
runbook, the reference-contract notes, the generated ABI surface -- into .docs_site/src/ (git-ignored), rewrites the
links that pointed at each other's old places, and turns links to source files into GitHub links at the current commit.
So the repo stays the source of truth and `tools/check_docs.py` keeps guarding it; the site is a view.

TWO LANGUAGES. English is authoritative. A translation lives BESIDE its source as `<name>.zh.md`, so its relative links are
the source's links and the link checker covers it; its first line records the git blob it was translated from
(`<!-- translation-of: README.md @ <git hash-object of the source> -->`). A page with no translation shows the English one. Every
build lists the translations whose source has changed since -- a stale Chinese SECURITY page is worse than none.

KEEP IT INTERNAL. SECURITY.md, AUDIT.md and emergency/ describe what is knowingly open and how the brakes work. Serve it
on localhost, or behind access control (Cloudflare Access, a VPN); do not publish it to a public host.
"""
import os, re, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, '.docs_site'); SRC = os.path.join(OUT, 'src')
REPO = 'https://github.com/keyuyuan/hedgefund'
LANGS = ['en', 'zh']                                                     # first = the authoritative one
NAV_ZH = {'Start here': '从这里开始', 'Overview (repo front page)': '总览（仓库首页）', 'Roadmap': '路线图', 'Build': '开发', 'Architecture': '架构', 'Development': '开发指南',
          'Contract reference (generated)': '合约参考（生成）', 'ABI surface for a front end (generated)': '前端接口表（生成）', 'Launch kit: story, templates, screens': '上线套件：叙事、模板、页面',
          'Ship and run': '上线与运维', 'Deployment': '部署', 'Operations': '运维', 'Emergency runbook': '紧急预案', 'Security': '安全', 'Security model': '安全模型', 'Audit record': '审计记录',
          'The stock token, assessed': '股票代币评估', 'Research': '研究', 'Rule backtests': '规则回测', 'Listing candidates': '上市候选', 'Pool selection': '池子选择',
          'Reference contracts (pons, PunkStrategy ...)': '参考合约（pons、PunkStrategy…）', 'Robinhood Chain docs (mirror)': 'Robinhood Chain 文档（镜像）', 'Index': '索引',
          'Building with stock tokens': '基于股票代币开发', 'Contracts': '合约地址', 'Oracles and price feeds': '预言机与喂价'}
# repo file -> page in the site
EXTRA = {'README.md': 'overview.md', 'AUDIT.md': 'audit.md', 'emergency/README.md': 'emergency.md', 'ref/CLAUDE.md': 'reference-contracts.md',
         'abi/SURFACE.md': 'abi-surface.md', 'LISTING_CANDIDATES.md': 'listing-candidates.md', 'POOL_SELECTION.md': 'pool-selection.md'}
NAV = [('Start here', 'README.md'), ('Overview (repo front page)', 'overview.md'), ('Roadmap', 'ROADMAP.md'),
       ('Build', [('Architecture', 'ARCHITECTURE.md'), ('Development', 'DEVELOPMENT.md'), ('Contract reference (generated)', 'REFERENCE.md'),
                  ('ABI surface for a front end (generated)', 'abi-surface.md'), ('Launch kit: story, templates, screens', 'LAUNCH_KIT.md')]),
       ('Ship and run', [('Production addresses', 'ADDRESSES.md'), ('Deployment', 'DEPLOYMENT.md'), ('Operations', 'OPERATIONS.md'), ('Emergency runbook', 'emergency.md')]),
       ('Security', [('Security model', 'SECURITY.md'), ('Audit record', 'audit.md'), ('The stock token, assessed', 'STOCK_TOKEN_ASSESSMENT.md')]),
       ('Research', [('Rule backtests', 'rule-backtest/README.md'), ('Listing candidates', 'listing-candidates.md'), ('Pool selection', 'pool-selection.md'),
                     ('Reference contracts (pons, PunkStrategy ...)', 'reference-contracts.md'), ('Robinhood Chain docs (mirror)', [('Index', 'robinhood-chain/README.md'), ('Building with stock tokens', 'robinhood-chain/building-with-stock-tokens.md'),
                        ('Contracts', 'robinhood-chain/contracts.md'), ('Oracles and price feeds', 'robinhood-chain/oracles-and-price-feeds.md')])])]

def commit(): return subprocess.check_output(['git', '-C', ROOT, 'rev-parse', 'HEAD']).decode().strip()

def assemble():
    shutil.rmtree(SRC, ignore_errors=True); shutil.copytree(os.path.join(ROOT, 'docs'), SRC)
    placed = {}                                                       # absolute repo path -> site-relative path
    for dp, _, fs in os.walk(os.path.join(ROOT, 'docs')):
        for f in fs: placed[os.path.join(dp, f)] = os.path.relpath(os.path.join(dp, f), os.path.join(ROOT, 'docs'))
    for repo_rel, page in EXTRA.items():
        p = os.path.join(ROOT, repo_rel)
        if os.path.exists(p): shutil.copy(p, os.path.join(SRC, page)); placed[p] = page
        for lang in LANGS[1:]:
            t = p[:-3] + '.%s.md' % lang
            if os.path.exists(t): tp = page[:-3] + '.%s.md' % lang; shutil.copy(t, os.path.join(SRC, tp)); placed[t] = tp
    sha = commit()
    for repo_abs, site_rel in list(placed.items()):
        if not site_rel.endswith('.md'): continue
        here = os.path.join(SRC, site_rel); text = open(here, encoding='utf-8').read()
        def fix(m):
            label, target = m.group(1), m.group(2)
            if re.match(r'^(https?:|mailto:|#)', target): return m.group(0)
            path, _, frag = target.partition('#')
            if not path: return m.group(0)
            dest = os.path.normpath(os.path.join(os.path.dirname(repo_abs), path))      # what it pointed at IN THE REPO
            if dest in placed:
                rel = os.path.relpath(os.path.join(SRC, placed[dest]), os.path.dirname(here))
            elif os.path.exists(dest):                                                   # source, tests, scripts, data: link to GitHub
                kind = 'tree' if os.path.isdir(dest) else 'blob'
                return '[%s](%s/%s/%s/%s%s)' % (label, REPO, kind, sha, os.path.relpath(dest, ROOT), ('#' + frag) if frag else '')
            else: return m.group(0)
            return '[%s](%s%s)' % (label, rel, ('#' + frag) if frag else '')
        text = re.sub(r'\[([^\]]*)\]\(([^)\s]+)\)', fix, text)
        open(here, 'w', encoding='utf-8').write(text)
    def nav(items, ind=0):
        out = []
        for title, v in items:
            if isinstance(v, list): out.append('%s- "%s":' % ('  ' * ind, title)); out += nav(v, ind + 1)
            elif os.path.exists(os.path.join(SRC, v)): out.append('%s- "%s": %s' % ('  ' * ind, title, v))
        return out
    yml = (['site_name: Strategy launchpad -- internal docs', 'site_description: assembled from the repo at %s' % sha[:10], 'docs_dir: src', 'site_dir: site',
           'repo_url: %s' % REPO, 'edit_uri: ""', 'theme:', '  name: material', '  features: [navigation.sections, navigation.top, search.highlight, search.suggest, content.code.copy, toc.follow]',
           '  palette:', '    - media: "(prefers-color-scheme: light)"', '      scheme: default', '      toggle: {icon: material/weather-night, name: dark}',
           '    - media: "(prefers-color-scheme: dark)"', '      scheme: slate', '      toggle: {icon: material/weather-sunny, name: light}',
           'plugins:', '  - search', '  - i18n:', '      docs_structure: suffix', '      fallback_to_default: true', '      reconfigure_material: true', '      reconfigure_search: true',
           '      languages:', '        - {locale: en, default: true, name: English, build: true}', '        - locale: zh', '          name: "中文"', '          build: true', '          nav_translations:']
          + ['            "%s": "%s"' % kv for kv in NAV_ZH.items()] + [ 'markdown_extensions:', '  - admonition', '  - tables', '  - toc: {permalink: true}', '  - pymdownx.highlight', '  - pymdownx.superfences:',
           '      custom_fences:', '        - name: mermaid', '          class: mermaid', '          format: !!python/name:pymdownx.superfences.fence_code_format',
           'validation: {links: {not_found: info, anchors: info, unrecognized_links: info}}', 'nav:'] + ['  ' + l for l in nav(NAV)])
    open(os.path.join(OUT, 'mkdocs.yml'), 'w', encoding='utf-8').write('\n'.join(yml) + '\n')
    stale = []
    for t, site_rel in placed.items():
        m = re.match(r'(.*)\.(%s)\.md$' % '|'.join(LANGS[1:]), t)
        if not m: continue
        first = open(t, encoding='utf-8').readline(); h = re.search(r'translation-of: \S+ @ ([0-9a-f]{40})', first); srcf = m.group(1) + '.md'
        now = subprocess.check_output(['git', '-C', ROOT, 'hash-object', srcf]).decode().strip() if os.path.exists(srcf) else None
        if not h or h.group(1) != now: stale.append(os.path.relpath(t, ROOT))
    print('translations: %d, STALE (source changed since): %s' % (sum(1 for t in placed if re.search(r'\.(%s)\.md$' % '|'.join(LANGS[1:]), t)), ', '.join(stale) or 'none'))

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'serve'
    if cmd not in ('serve', 'build', 'assemble'): sys.exit(__doc__)
    assemble(); print('assembled', os.path.relpath(SRC, ROOT), 'at', commit()[:10])
    if cmd != 'assemble': sys.exit(subprocess.call([sys.executable, '-m', 'mkdocs', cmd, '-f', os.path.join(OUT, 'mkdocs.yml')] + sys.argv[2:]))
