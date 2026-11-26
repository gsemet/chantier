# Claude Code: the two command lines

Put the rules in place of `'<rule 1>','<rule 2>'`; each line was run by hand and read back as
`P10 ok`.

Windows PowerShell 5.1 (rewrites the file as compact JSON):

```powershell
Add-Type -AssemblyName System.Web.Extensions; $r = '<rule 1>','<rule 2>'; $p = Join-Path $HOME '.claude\settings.json'; $js = New-Object System.Web.Script.Serialization.JavaScriptSerializer; $d = if (Test-Path $p) { $js.DeserializeObject([IO.File]::ReadAllText($p, [Text.Encoding]::UTF8)) } else { @{} }; if (-not $d.ContainsKey('permissions')) { $d['permissions'] = @{} }; if (-not $d['permissions'].ContainsKey('allow')) { $d['permissions']['allow'] = @() }; $a = @($d['permissions']['allow']); foreach ($x in $r) { if ($a -notcontains $x) { $a += $x } }; $d['permissions']['allow'] = $a; New-Item -ItemType Directory -Force (Split-Path $p) | Out-Null; [IO.File]::WriteAllText($p, $js.Serialize($d), (New-Object Text.UTF8Encoding $false))
```

POSIX shell (needs `uv`; two-space indent):

```sh
uv run --no-project python -c 'import json,os,sys;p=os.path.expanduser("~/.claude/settings.json");d=json.load(open(p,encoding="utf-8-sig")) if os.path.exists(p) else {};a=d.setdefault("permissions",{}).setdefault("allow",[]);a+=[r for r in dict.fromkeys(sys.argv[1:]) if r not in a];s=json.dumps(d,indent=2,ensure_ascii=False)+"\n";os.makedirs(os.path.dirname(p),exist_ok=True);open(p,"w",encoding="utf-8",newline="\n").write(s)' '<rule 1>' '<rule 2>'
```

[Trials](../../../../docs/proofs/claude-code.md#allow-rules-to-add)
