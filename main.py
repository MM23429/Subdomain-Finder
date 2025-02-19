import streamlit as st
from crtsh import crtshAPI
import pandas as pd
import asyncio
import aiohttp

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
    Performs asynchronous HTTP checks on a list of subdomains and updates progress.
    """
    results = []
    async with aiohttp.ClientSession() as session:
        tasks = [check_subdomain(session, sub) for sub in subdomain_list]
        total = len(tasks)
        for i, future in enumerate(asyncio.as_completed(tasks)):
            result = await future
            results.append(result)
            progress_callback((i + 1) / total)
    return results

def main():
    st.title("Subdomain Finder")
    st.write("This tool searches crt.sh for subdomains of a given domain and then performs HTTP checks to determine if they are online. Searches are dependent on crt.sh, they somtimes may fail, try another domain then try again if this happens.")
    
    domain = st.text_input("Enter a naked domain (e.g. example.com):")
    
    if st.button("Search") and domain:
        with st.spinner(text=f"Searching for subdomains of {domain}... This can take a while."):
            try:
                data = crtshAPI().search(domain)
                if not data:
                    st.error("No data returned from crt.sh. The domain may not have any certificate records or the API might be unavailable. (Try another domain and then try again)")
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
                def update_progress(value):
                    progress_bar.progress(value)
                
                # Perform asynchronous HTTP checks.
                results = asyncio.run(perform_http_checks(subdomain_list, update_progress))
                # Prepare online results without error details.
                online_results = [{"Subdomain": res["Subdomain"], "Status": res["Status"]} 
                                  for res in results if "Live" in res["Status"]]
                # Offline results include error details.
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
