# BGP Lab2 Web UI

A small Flask app I threw together to make it easier to see what's going on across all 4 routers without juggling terminal windows.

It talks to the VMs through `vagrant ssh` and `vtysh` under the hood — nothing fancy.

## What it does

- Shows the full mesh topology with live peer status
- Click a router to see its BGP summary, route table, route-maps, and prefix-lists
- Push config lines directly from the browser (it wraps them in `configure terminal` / `end`)
- Run any `show` command on any router

## How to run

```bash
cd lab2
pip install -r web/requirements.txt
python web/app.py
```

Then open http://localhost:5000. The VMs need to be up (`vagrant up`).

## Screenshots

![Overview](../image/web1.png)
![Router detail](../image/web2.png)
![Config push](../image/web3.png)
![Show commands](../image/web4.png)
