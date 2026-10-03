import socket,time,urllib.request,urllib.parse,xml.etree.ElementTree as ET,concurrent.futures,ipaddress
NS={'d':'urn:schemas-upnp-org:device-1-0'}
def describe(url):
 try:
  host=urllib.parse.urlparse(url).hostname
  if ipaddress.ip_address(host) not in ipaddress.ip_network('@LAN_NETWORK@'):return None
  with urllib.request.urlopen(url,timeout=4) as r:root=ET.fromstring(r.read(262144))
  for device in root.findall('.//d:device',NS):
   for service in device.findall('d:serviceList/d:service',NS):
    kind=service.findtext('d:serviceType','',NS)
    if ':AVTransport:' in kind:
     control=urllib.parse.urljoin(url,service.findtext('d:controlURL','',NS))
     if urllib.parse.urlparse(control).hostname!=host:return None
     result={'name':device.findtext('d:friendlyName',host,NS),'ip':host,'control':control,'service':kind}
     for other in device.findall('d:serviceList/d:service',NS):
      if ':RenderingControl:' in other.findtext('d:serviceType','',NS):
       endpoint=urllib.parse.urljoin(url,other.findtext('d:controlURL','',NS))
       if urllib.parse.urlparse(endpoint).hostname==host:
        result['render_control']=endpoint;result['render_service']=other.findtext('d:serviceType','',NS)
     return result
 except Exception:pass
 return None
def discover(manual=None):
 if manual and ipaddress.ip_address(manual) not in ipaddress.ip_network('@LAN_NETWORK@'):raise ValueError('Device must be on the configured LAN subnet.')
 urls=set();s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.settimeout(.3)
 s.bind(('@LAN_IP@',0))
 msg=b'M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: "ssdp:discover"\r\nMX: 2\r\nST: urn:schemas-upnp-org:device:MediaRenderer:1\r\n\r\n'
 s.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_IF,socket.inet_aton('@LAN_IP@'))
 s.sendto(msg,('239.255.255.250',1900));end=time.monotonic()+3
 while time.monotonic()<end:
  try:
   data,addr=s.recvfrom(16384)
   for line in data.decode(errors='replace').splitlines():
    if line.lower().startswith('location:'):urls.add(line.split(':',1)[1].strip())
  except socket.timeout:pass
 s.close()
 # Samsung discovery fallback when multicast is filtered; read-only LAN probes.
 hosts=[str(ipaddress.ip_address(manual))] if manual else [str(ip) for ip in ipaddress.ip_network('@LAN_NETWORK@').hosts()]
 def samsung(host):
  sock=socket.socket();sock.settimeout(1)
  try:sock.connect((host,9197));return 'http://'+host+':9197/dmr'
  except OSError:return None
  finally:sock.close()
 with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
  urls.update(u for u in pool.map(samsung,hosts) if u)
 if manual:
  urls.update(f'http://{hosts[0]}:{port}/{path}' for port,path in [(1400,'xml/device_description.xml'),(49152,'description.xml'),(8008,'ssdp/device-desc.xml')])
 with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
  devices=[d for d in pool.map(describe,urls) if d]
 return list({d['control']:d for d in devices}.values())
if __name__=='__main__':
 import json,sys;print(json.dumps(discover(sys.argv[1] if len(sys.argv)>1 else None),indent=2))
