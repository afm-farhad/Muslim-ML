import requests
import pandas as pd
import os
import time
import random
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")

if not API_KEY:
    raise ValueError("❌ API Key not found. Please set OPENROUTER_API_KEY in .env")
else:
    print("✅ API Key loaded:", API_KEY[:8], "…")



API_URL = "https://openrouter.ai/api/v1/chat/completions"

if not API_KEY:
    raise ValueError("API Key not found.")

models = [
    "deepseek/deepseek-chat-v3.1:free",
    "google/gemini-2.0-flash-exp:free",
    "meta-llama/llama-3.3-70b-instruct:free"
]

sheet_id = "1yLfUbxmEBlaXFxb2Etd51lIQ0YdPtbBLmVAYzdQYoTs"
gid = "0"
google_sheet_url = (
    f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?"
    f"tqx=out:csv&gid={gid}"
)

question_column_name = "Question (Bengali)"


PROMPT = (
    "আপনি একজন অভিজ্ঞ মুসলিম আইন বিশেষজ্ঞ। "
    "আপনার কাজ হলো ব্যবহারকারীর প্রশ্নের উত্তর কোরআন, হাদীস, এবং ইসলামের আলোকে প্রদান করা। "
    "উত্তরগুলি সংক্ষিপ্ত, স্পষ্ট এবং সঠিক হওয়া উচিত, সর্বোচ্চ ৪–৫ লাইনের মধ্যে সীমাবদ্ধ রাখুন। "
    "অনুমান বা ব্যক্তিগত মতামত দেওয়া থেকে বিরত থাকুন। "
    "প্রত্যেকটি উত্তর অবশ্যই বাংলায় দিবেন।\n\n"
    "প্রত্যেক উত্তরের ফরম্যাট:\n"
    "Answer:\n<সংক্ষিপ্ত উত্তর এখানে>\n\n"
    "References:\n<প্রাসঙ্গিক আয়াত বা হাদীসের নম্বর এখানে>\n\n"
    "প্রশ্ন: {}"
)

def query_model(question, model, retries=5, delay=5, timeout=60):
    """
    Query a model with retries and capped exponential backoff for 429 errors.
    """
    for attempt in range(1, retries + 1):
        try:
            headers = {
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost",
                "X-Title": "Free QA Experiment"
            }

            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": PROMPT},
                    {"role": "user", "content": question}
                ]
            }

            response = requests.post(API_URL, headers=headers, json=payload, timeout=timeout)
            
            if response.status_code == 429:
                wait_time = min(delay * (2 ** attempt), 60)
                print(f"⚠️ Rate limit hit for {model}, retrying in {wait_time:.0f}s...")
                time.sleep(wait_time)
                continue
            elif response.status_code >= 400:
                response.raise_for_status()
            
            resp_json = response.json()
            return resp_json["choices"][0]["message"]["content"]

        except requests.exceptions.RequestException as e:
            print(f"⚠️ Attempt {attempt} failed for {model}: {e}")
            time.sleep(min(delay * (2 ** attempt), 60))
        except Exception as e:
            print(f"⚠️ Unexpected error for {model}: {e}")
            return "Failed"
    
    return "Failed"

def process_question_for_all_models(question):
    """Query all models sequentially for a single question"""
    results = {"question": question}
    print(f"\n❓ Processing question: {question[:50]}...")

    for model in models:
        answer = query_model(question, model)
        results[model] = answer
        print(f"   → Finished {model}: {'Success' if answer != 'Failed' else 'Failed'}")
        time.sleep(5 + random.uniform(0, 3))

    return results


try:
    print(f"📥 Loading data from Google Sheet: {google_sheet_url}")
    df = pd.read_csv(google_sheet_url)
    initial = 1
    final = 2
    # Use the specified slice of the DataFrame
    df = df.iloc[initial:final]

    if question_column_name not in df.columns:
        raise ValueError(f"Column '{question_column_name}' not found in Google Sheet.")
except Exception as e:
    raise RuntimeError(f"Failed to load Google Sheet: {e}")

all_results = []
batch_size = 1
sleep_between_batches = 60

for i in range(0, len(df), batch_size):
    batch_df = df.iloc[i:i + batch_size]
    print(f"\n📦 Processing batch {i // batch_size + 1} ({len(batch_df)} questions)...")

    for idx, row in batch_df.iterrows():
        question = row[question_column_name]
        batch_results = process_question_for_all_models(question)
        print(batch_results)
        all_results.append(batch_results)
        pd.DataFrame(all_results).to_csv("answers_free_partial.csv", index=False, encoding="utf-8-sig")
    
    print(f"⏸ Pausing {sleep_between_batches}s to respect free-tier limits...")
    time.sleep(sleep_between_batches)

results_df = pd.DataFrame(all_results)
results_df.to_csv("answers_free.csv", index=False, encoding="utf-8-sig")
print("\n✅ Finished! All answers saved in 'answers_free.csv'.")