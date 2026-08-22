import psutil, time
from typing import Dict, Any, List, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from utils.sizes import format_size

DEV_PORTS = {
    3000:"React/Node.js",3001:"React alt",4200:"Angular",5000:"Flask",
    5001:"Flask alt",5173:"Vite",8000:"Django",8080:"HTTP alt",
    8443:"HTTPS alt",8888:"Jupyter",9000:"PHP-FPM",9229:"Node debugger",
    4000:"Jekyll",1337:"Strapi",4321:"Astro",7860:"Gradio",6006:"TensorBoard"
}
PROTECTED = {"system","smss.exe","csrss.exe","wininit.exe","winlogon.exe",
             "services.exe","lsass.exe","svchost.exe","dwm.exe","explorer.exe",
             "taskmgr.exe","ntoskrnl.exe","registry","idle"}

def scan_processes_and_ports(console=None) -> Dict[str,Any]:
    res={"zombie":[],"orphan":[],"idle_heavy":[],"high_cpu":[],"high_mem":[],
         "duplicate":[],"blocked_ports":[],"all_ports":[],"summary":{}}

    pid_set=set()
    all_procs=[]
    for p in psutil.process_iter(["pid","name","status","ppid","memory_info","create_time","username","exe"]):
        try: info=p.info; pid_set.add(info["pid"]); all_procs.append(info)
        except: pass

    # CPU — 2 muestras
    cpu_map={}
    live={p.pid:p for p in psutil.process_iter() if p.pid in pid_set}
    for p in live.values():
        try: p.cpu_percent(interval=None)
        except: pass
    time.sleep(1.5)
    for pid,p in live.items():
        try: cpu_map[pid]=p.cpu_percent(interval=None)
        except: cpu_map[pid]=0.0

    name_groups={}
    killable_ram=0
    now=time.time()

    for info in all_procs:
        pid=info.get("pid",0); name=(info.get("name") or "").lower()
        if name in PROTECTED or pid in (0,4): continue
        status=info.get("status",""); ppid=info.get("ppid",0)
        mem=info.get("memory_info"); ram_mb=round(mem.rss/1024/1024,1) if mem else 0
        cpu=cpu_map.get(pid,0.0); ctime=info.get("create_time",now)
        uptime=now-ctime

        bn=name.replace(".exe","")
        name_groups.setdefault(bn,[]).append(info)

        entry={"pid":pid,"name":name,"status":status,"ram_mb":ram_mb,"cpu":cpu,
               "uptime_min":round(uptime/60,1)}

        if status==psutil.STATUS_ZOMBIE:
            res["zombie"].append(entry); killable_ram+=ram_mb
        elif ppid!=0 and ppid not in pid_set:
            res["orphan"].append(entry); killable_ram+=ram_mb
        elif ram_mb>=200 and cpu<=0.5 and uptime>300:
            res["idle_heavy"].append(entry); killable_ram+=ram_mb

        if cpu>=15: res["high_cpu"].append(entry)
        if ram_mb>=300: res["high_mem"].append(entry)

    for bn,procs in name_groups.items():
        if len(procs)>=4 and bn not in ("svchost","conhost","runtimebroker","backgroundtaskhost"):
            res["duplicate"].append({"name":bn,"count":len(procs),
                "total_ram_mb":round(sum(p.get("memory_info").rss/1024/1024 if p.get("memory_info") else 0 for p in procs),1),
                "pids":[p["pid"] for p in procs]})

    try:
        for c in psutil.net_connections(kind="inet"):
            if c.status==psutil.CONN_LISTEN and c.laddr:
                port=c.laddr.port
                pname="?"
                try:
                    if c.pid: pname=psutil.Process(c.pid).name()
                except: pass
                entry={"port":port,"pid":c.pid,"process":pname,
                       "is_dev":port in DEV_PORTS,"service":DEV_PORTS.get(port,"")}
                res["all_ports"].append(entry)
                if port in DEV_PORTS: res["blocked_ports"].append(entry)
    except: pass

    total_ram=sum(p.get("memory_info").rss/1024/1024 if p.get("memory_info") else 0 for p in all_procs)
    res["summary"]={"total":len(all_procs),"ram_mb":round(total_ram,1),
                    "killable_mb":round(killable_ram,1),"blocked_ports":len(res["blocked_ports"])}
    for key in ("zombie","orphan","idle_heavy","high_cpu","high_mem"):
        res[key].sort(key=lambda x:x.get("ram_mb",0),reverse=True)
    return res

def show_process_report(data: Dict, console: Console):
    s=data.get("summary",{})
    console.print(Panel(
        f"  🖥  Procesos activos:      [bold]{s.get('total',0)}[/]\n"
        f"  💾 RAM total en uso:      [bold cyan]{s.get('ram_mb',0):.0f} MB[/]\n"
        f"  🎯 RAM potencialmente liberable: [bold green]{s.get('killable_mb',0):.0f} MB[/]\n"
        f"  🔌 Puertos dev bloqueados: [bold magenta]{s.get('blocked_ports',0)}[/]",
        title="[bold white]📊 Procesos y Puertos[/]",border_style="cyan"))

    def ptable(title,items,color):
        if not items: return
        t=Table(title=f"[bold {color}]{title}[/]",box=box.SIMPLE_HEAD,header_style=f"bold {color}")
        t.add_column("PID",width=8,justify="right")
        t.add_column("Proceso",width=28)
        t.add_column("RAM",width=10,justify="right")
        t.add_column("CPU%",width=8,justify="right")
        t.add_column("Uptime",width=14)
        t.add_column("Estado",width=12)
        for p in items[:12]:
            ram=p.get("ram_mb",0); cpu=p.get("cpu",0)
            t.add_row(str(p["pid"]),p["name"],
                f"[{'red' if ram>500 else 'yellow' if ram>200 else 'white'}]{ram:.0f} MB[/]",
                f"[{'red' if cpu>50 else 'yellow' if cpu>15 else 'white'}]{cpu:.1f}%[/]",
                f"{p.get('uptime_min',0):.0f} min",p.get("status","?"))
        console.print(t)

    ptable("💀 Procesos Zombie",data["zombie"],"red")
    ptable("👻 Procesos Huérfanos (padre muerto)",data["orphan"],"yellow")
    ptable("🧟 Ociosos con Alto Consumo (>200MB RAM, CPU≈0)",data["idle_heavy"],"yellow")
    ptable("🔥 Alto CPU (>15%)",data["high_cpu"][:8],"red")
    ptable("💾 Alto Consumo RAM (>300MB)",data["high_mem"][:8],"magenta")

    if data["duplicate"]:
        t=Table(title="[bold yellow]🔁 Procesos Duplicados[/]",box=box.SIMPLE_HEAD,header_style="bold yellow")
        t.add_column("Proceso",width=26); t.add_column("Instancias",width=12,justify="right")
        t.add_column("RAM Total",width=14,justify="right"); t.add_column("PIDs",min_width=30)
        for d in data["duplicate"]:
            pids=", ".join(str(p) for p in d["pids"][:6])
            t.add_row(d["name"],f"[yellow]{d['count']}x[/]",f"{d['total_ram_mb']:.0f} MB",f"[dim]{pids}[/]")
        console.print(t)

    if data["blocked_ports"]:
        t=Table(title="[bold magenta]🔌 Puertos de Desarrollo Bloqueados[/]",box=box.SIMPLE_HEAD,header_style="bold magenta")
        t.add_column("Puerto",width=10,justify="right"); t.add_column("Framework",width=20)
        t.add_column("Proceso",width=22); t.add_column("PID",width=8,justify="right")
        for p in data["blocked_ports"]:
            t.add_row(f"[bold magenta]:{p['port']}[/]",p.get("service",""),p.get("process","?"),str(p.get("pid","?")))
        console.print(t)

    if data["all_ports"]:
        t=Table(title="[dim]🌐 Todos los Puertos en Escucha[/]",box=box.MINIMAL,header_style="bold dim")
        t.add_column("Puerto",width=8,justify="right"); t.add_column("Proceso",width=24)
        t.add_column("PID",width=8,justify="right"); t.add_column("Tipo",width=20)
        for p in sorted(data["all_ports"],key=lambda x:x["port"])[:30]:
            is_dev=p.get("is_dev",False)
            t.add_row(f"[{'magenta' if is_dev else 'dim'}]:{p['port']}[/]",
                p.get("process","?"),str(p.get("pid","?")),
                f"[magenta]DEV: {p.get('service','')}[/]" if is_dev else "[dim]Sistema[/]")
        console.print(t)

def kill_process(pid,force=False) -> Tuple[bool,str]:
    try:
        p=psutil.Process(pid)
        if p.name().lower() in PROTECTED: return False,f"Proceso protegido: {p.name()}"
        p.kill() if force else p.terminate()
        gone,_=psutil.wait_procs([p],timeout=3)
        return (True,f"PID {pid} terminado.") if gone else (False,"No respondió. Intenta force=True.")
    except psutil.NoSuchProcess: return True,f"PID {pid} ya no existe."
    except psutil.AccessDenied: return False,f"Acceso denegado para PID {pid}. Ejecuta como Admin."
    except Exception as e: return False,str(e)

def interactive_process_cleanup(data,console) -> Dict:
    report={"killed":[],"released_ports":[],"errors":[]}
    killable=data["zombie"]+data["orphan"]+data["idle_heavy"]
    if killable:
        console.print(Panel("[bold yellow]Terminar Procesos Problemáticos[/]\nIngresa PIDs separados por coma o ENTER para omitir.",border_style="yellow"))
        try: raw=input("  PIDs a terminar: ").strip()
        except: return report
        if raw:
            for pid in [int(x) for x in raw.split(",") if x.strip().isdigit()]:
                ok,msg=kill_process(pid)
                if ok: report["killed"].append(pid); console.print(f"  ✅ {msg}")
                else:
                    console.print(f"  ⚠️  {msg}")
                    try:
                        if input(f"  ¿Forzar cierre de PID {pid}? (s/N): ").strip().lower()=="s":
                            ok2,msg2=kill_process(pid,force=True)
                            if ok2: report["killed"].append(pid); console.print(f"  ✅ {msg2}")
                            else: report["errors"].append(msg2)
                    except: pass

    if data["blocked_ports"]:
        console.print(Panel("[bold magenta]Liberar Puertos de Desarrollo[/]\nIngresa puertos separados por coma o ENTER para omitir.",border_style="magenta"))
        try: raw=input("  Puertos a liberar: ").strip()
        except: return report
        if raw:
            for port in [int(x) for x in raw.split(",") if x.strip().isdigit()]:
                pid=next((p["pid"] for p in data["blocked_ports"] if p["port"]==port),None)
                if pid:
                    ok,msg=kill_process(pid)
                    if ok: report["released_ports"].append(port); console.print(f"  ✅ Puerto :{port} liberado")
                    else: console.print(f"  ❌ {msg}")
    return report
