#!/usr/bin/env python3
"""Observe TLS certificate acceptance on an isolated camera network."""
import argparse,json,socket,ssl,time
from concurrent.futures import ThreadPoolExecutor

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bind",required=True);p.add_argument("--port",type=int,default=443)
    p.add_argument("--cert",required=True);p.add_argument("--key",required=True)
    a=p.parse_args();ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version=ssl.TLSVersion.TLSv1_2;ctx.load_cert_chain(a.cert,a.key)
    def log(**values):print(json.dumps({"time":time.time(),**values}),flush=True)
    ctx.set_servername_callback(lambda sock,name,context:log(event="sni",name=name))
    def handle(conn):
        try:
            conn.settimeout(8)
            with ctx.wrap_socket(conn,server_side=True) as tls:
                log(event="handshake_accepted",version=tls.version())
                data=tls.recv(4096);log(event="application_data",bytes=len(data))
                tls.sendall(b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
        except Exception as e:log(event="connection_failed",error=str(e))
        finally:conn.close()
    with socket.socket() as server,ThreadPoolExecutor(max_workers=4) as workers:
        server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        server.bind((a.bind,a.port));server.listen(4)
        log(event="listening",port=a.port)
        while True:
            conn,_=server.accept();workers.submit(handle,conn)
if __name__=="__main__":main()
