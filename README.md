Run setup.sh on both the server and client computers if this is your first time cloning this repo.

On the server (host to which camera is connected), run:
```
python3 camera.py server
```

On the client (viewing host), run:
```
python3 camera.py viewer [hostname]
```
where [hostname] is the output you get when you run ```hostname``` in the terminal.
P.S. Don't forget to remove the sqaure brackets. They're just a connotation I use for variables.
