import streamlit as st
from pycrtsh import Crtsh
import pandas as pd
import asyncio
import aiohttp
import time

async def check_subdomain(session, subdomain):
   """
   Asynchronously checks a single subdomain and records error details if any.
   """
   url = f"http://{subdomain}"
   try:
       async with session.get(url, timeout=3) as response:
           if response.status < 400:
               return {"Subdomain": subdomain, "Status": f"Live ({response.status})", "Error": ""}
           else:
               return {"Subdomain": subdomain, "Status": f"Down ({response.status})", "Error": f"HTTP Error {response.status}"}
   except Exception as e:
       return {"Subdomain": subdomain, "Status": "Down (Error)", "Error": str(e)}

async def perform_http_checks(subdomain_list, progress_callback):
   """
   Performs asynchronous HTTP checks on a list of subdomains.
   After each task, calculates and updates the estimated remaining time.
   """
   results = []
   start_time = time.perf_counter()
   async with aiohttp.ClientSession() as session:
       tasks = [check_subdomain(session, sub) for sub in subdomain_list]
       total = len(tasks)
       for i, future in enumerate(asyncio.as_completed(tasks)):
           result = await future
           results.append(result)
           # Calculate estimated remaining time.
           elapsed = time.perf_counter() - start_time
           tasks_completed = i + 1
           avg_time = elapsed / tasks_completed
           remaining_tasks = total - tasks_completed
           eta = avg_time * remaining_tasks
           progress_callback(tasks_completed / total, eta)
   return results

def main():
   st.title("crt.sh Subdomain Search with Async HTTP Check, ETA & CSV Download")
   
   domain = st.text_input("Enter a naked domain (e.g. example.com):")
   
   if st.button("Search") and domain:
       with st.spinner(text=f"Searching crt.sh for subdomains of {domain}..."):
           try:
               crtsh = Crtsh()
               data = crtsh.search(domain)
               if not data:
                   st.error("No data returned from crt.sh. The domain may not have any certificate records or the API might be unavailable.")
                   return
               
               subdomains = set()
               for entry in data:
                   # 'name_value' may contain multiple subdomains separated by newlines.
                   names = entry.get("name_value", "").splitlines()
                   for sub in names:
                       sub = sub.strip()
                       if sub.endswith(domain):
                           subdomains.add(sub)
               subdomain_list = list(subdomains)
               st.write(f"Found {len(subdomain_list)} unique subdomains.")
               
               progress_bar = st.progress(0)
               eta_placeholder = st.empty()
               
               def update_progress(progress_value, eta):
                   progress_bar.progress(progress_value)
                   eta_placeholder.text(f"Estimated time remaining: {eta:.1f} seconds")
               
               # Run asynchronous HTTP checks.
               results = asyncio.run(perform_http_checks(subdomain_list, update_progress))
               
               # Separate results: online without error details, offline with error details.
               online_results = [{"Subdomain": res["Subdomain"], "Status": res["Status"]} 
                                 for res in results if "Live" in res["Status"]]
               offline_results = [res for res in results if "Down" in res["Status"]]
               
               st.subheader("Online Subdomains")
               if online_results:
                   df_online = pd.DataFrame(online_results)
                   st.write(df_online)
                   csv_online = df_online.to_csv(index=False).encode("utf-8")
                   st.download_button(
                       label="Download Online CSV",
                       data=csv_online,
                       file_name="online_subdomains.csv",
                       mime="text/csv"
                   )
               else:
                   st.write("No online subdomains found.")
               
               st.subheader("Offline Subdomains")
               if offline_results:
                   df_offline = pd.DataFrame(offline_results)
                   st.write(df_offline)
                   csv_offline = df_offline.to_csv(index=False).encode("utf-8")
                   st.download_button(
                       label="Download Offline CSV",
                       data=csv_offline,
                       file_name="offline_subdomains.csv",
                       mime="text/csv"
                   )
               else:
                   st.write("No offline subdomains found.")
           except Exception as e:
               st.error(f"An error occurred: {e}")

if __name__ == "__main__":
   main()
