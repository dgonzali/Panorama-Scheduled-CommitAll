import os
import time
import requests
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

# Load configuration from .env
load_dotenv()

PAN_URL = os.getenv('PAN_URL')
api_key = os.getenv('PAN_API_KEY')

if not PAN_URL or not api_key:
    print("Error: PAN_URL and PAN_API_KEY must be defined in the .env file.")
    exit(1)

# Toggle for manual confirmation (useful for automation)
# Can be set to 'false' in .env to disable confirmation
REQUIRE_CONFIRMATION = os.getenv('REQUIRE_CONFIRMATION', 'true').lower() == 'true'

def get_out_of_sync_devices():
    """Queries Panorama for device groups and identifies out-of-sync devices."""
    print(f"Querying Panorama at {PAN_URL} for out-of-sync devices...")
    
    cmd = "<show><devicegroups></devicegroups></show>"
    url = f"{PAN_URL.rstrip('/')}/api/?type=op&cmd={cmd}"
    headers = {"X-PAN-KEY": api_key}
    
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=30)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        if root.attrib.get('status') != 'success':
            print("Error in API response:")
            print(response.text)
            return []
        
        out_of_sync_list = []
        
        # Iterate through device groups
        for dg_entry in root.findall(".//devicegroups/entry"):
            dg_name = dg_entry.get('name')
            
            # Find devices within this device group
            for device_entry in dg_entry.findall(".//devices/entry"):
                serial = device_entry.get('name')
                connected = device_entry.findtext('connected')
                policy_status = device_entry.findtext('shared-policy-status')
                
                if policy_status == 'Out of Sync':
                    out_of_sync_list.append({
                        'dg': dg_name,
                        'serial': serial,
                        'connected': connected
                    })
                    
        return out_of_sync_list

    except Exception as e:
        print(f"An error occurred while fetching device groups: {e}")
        return []

def execute_commit_all(devices_to_sync):
    """Triggers a commit-all for the provided devices grouped by their Device Groups."""
    
    # Group devices by Device Group to build the XML structure
    grouped = {}
    for dev in devices_to_sync:
        dg = dev['dg']
        if dg not in grouped:
            grouped[dg] = []
        grouped[dg].append(dev['serial'])
    
    # Build XML cmd
    # <commit-all>
    #   <shared-policy>
    #     <device-group>
    #       <entry name="DG1"><devices><entry name="S1"/></devices></entry>
    #     </device-group>
    #     ...
    #   </shared-policy>
    # </commit-all>
    
    commit_xml = "<commit-all><shared-policy><device-group>"
    for dg, serials in grouped.items():
        commit_xml += f'<entry name="{dg}"><devices>'
        for serial in serials:
            commit_xml += f'<entry name="{serial}"/>'
        commit_xml += "</devices></entry>"
    
    commit_xml += "</device-group>"
    commit_xml += "<include-template>no</include-template>"
    commit_xml += "<include-firewall-cluster>no</include-firewall-cluster>"
    commit_xml += "<merge-with-candidate-cfg>yes</merge-with-candidate-cfg>"
    commit_xml += "<force-template-values>no</force-template-values>"
    commit_xml += "<validate-only>no</validate-only>"
    commit_xml += "</shared-policy></commit-all>"
    
    url = f"{PAN_URL.rstrip('/')}/api/?type=commit&action=all&cmd={commit_xml}"
    headers = {"X-PAN-KEY": api_key}
    
    print("\nSending commit-all request...")
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=30)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        if root.attrib.get('status') == 'success':
            job_id = root.findtext(".//job")
            print(f"Commit-all enqueued. Job ID: {job_id}")
            return job_id
        else:
            print("Commit-all failed to enqueue:")
            print(response.text)
            return None
            
    except Exception as e:
        print(f"An error occurred during commit-all: {e}")
        return None

def monitor_job(job_id):
    """Monitors the job status every 10 seconds until it finishes."""
    print(f"\nMonitoring Job {job_id}...")
    
    cmd = f"<show><jobs><id>{job_id}</id></jobs></show>"
    url = f"{PAN_URL.rstrip('/')}/api/?type=op&cmd={cmd}"
    headers = {"X-PAN-KEY": api_key}
    
    while True:
        try:
            response = requests.get(url, headers=headers, verify=False, timeout=30)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            job_node = root.find(".//job")
            
            if job_node is None:
                print("Could not find job information in response.")
                break
                
            status = job_node.findtext('status')
            result = job_node.findtext('result')
            progress = job_node.findtext('progress')
            
            print(f"Job {job_id}: Status={status}, Result={result}, Progress={progress}%")
            
            if status == 'FIN':
                return job_node
            
            time.sleep(10)
            
        except Exception as e:
            print(f"Error monitoring job: {e}")
            time.sleep(10)

def display_final_summary(job_node):
    """Parses the finished job node and displays the final operation result."""
    print("\n" + "="*50)
    print("RESULTADO DE LA OPERACION:")
    print("="*50)
    
    # The XML structure for finished job contains <devices> with <entry>
    devices = job_node.findall(".//devices/entry")
    
    if not devices:
        print("No device details found in the job report.")
        # Try to fallback to top level result if devices list is empty
        overall_result = job_node.findtext('result')
        overall_status = job_node.findtext('status')
        print(f"Result: {overall_result} | Status: {overall_status}")
    
    for device in devices:
        serial = device.findtext('serial-no')
        # In some cases the DG name might be in the details/msg or elsewhere
        # From user example, it's typically in the details/msg metadata
        dg_name = "Unknown"
        msg_node = device.find(".//msg")
        if msg_node is not None:
             dg_name = msg_node.attrib.get('dgname', "Unknown")
        
        status = device.findtext('status')
        result = device.findtext('result')
        
        print(f"Device Group = {dg_name} | Devices = {serial} | Result: {result} | Status: {status}")
    print("="*50 + "\n")

def main():
    # 1. Fetch Out-of-Sync Devices
    devices = get_out_of_sync_devices()
    
    if not devices:
        print("\nNo hay equipos en out-of-sync.")
        return

    # 2. Display summary and ask confirmation
    print("\nLos Devices groups que estan en out of service son:\n")
    for dev in devices:
        print(f"Device Group = {dev['dg']} | Devices = {dev['serial']} | Connected: {dev['connected']}")
    
    if REQUIRE_CONFIRMATION:
        user_input = input("\nQuieres hacer el commit all a los equipos arriba indicados? (Y/N): ").strip().upper()
        if user_input != 'Y':
            print("Operación cancelada por el usuario.")
            return
    else:
        print("\nModo automático detectado. Procediendo con el commit-all...")

    # 3. Trigger Commit-All
    job_id = execute_commit_all(devices)
    
    if job_id:
        # 4. Monitor Job
        finished_job_node = monitor_job(job_id)
        
        # 5. Final results
        if finished_job_node is not None:
            display_final_summary(finished_job_node)
        else:
            print("El monitoreo del job falló.")

if __name__ == "__main__":
    # Disable insecure request warnings for self-signed certificates (common in Panorama)
    requests.packages.urllib3.disable_warnings()
    main()
