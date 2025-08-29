import requests
import os
import re
from datetime import datetime, timezone, timedelta
import time
from urllib.parse import urljoin
from bs4 import BeautifulSoup

# ★★★ Windowsでのコンソール文字化け対策 ★★★
os.environ['PYTHONUTF8'] = '1'

# アクセス先のURL定義
BASE_URL = "https://www.release.tdnet.info"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Referer': 'https://www.release.tdnet.info/inbs/I_main_00.html'
}

def sanitize_filename(filename):
    """ファイル名として使えない文字を安全な文字に置換する"""
    invalid_chars = r'[\\/:*?"<>|]'
    return re.sub(invalid_chars, lambda m: {'\\':'＼','/':'／',':':'：','*':'＊','?':'？','"':'”','<':'＜','>':'＞','|':'｜'}[m.group(0)], filename)

def get_disclosure_links(date):
    """指定日の開示情報（PDFリンク）を全ページから取得し、フィルタリングする"""
    all_pdf_links = []
    page_num = 1
    date_str = date.strftime('%Y%m%d')
    print(f"--- {date.strftime('%Y年%m月%d日')} のデータ取得を開始します ---")
    while True:
        try:
            content_url = f"https://www.release.tdnet.info/inbs/I_list_{page_num:03d}_{date_str}.html"
            print(f"[{page_num}ページ目] {content_url} にアクセスします...")
            response = requests.get(content_url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser', from_encoding='MS932')
            result_table = soup.find('table', id='main-list-table')
            if not result_table:
                if page_num == 1: print("開示情報が見つかりませんでした。")
                else: print("次のページは見つかりませんでした。情報の取得を完了します。")
                break
            rows = result_table.find_all('tr')
            if not rows:
                print("このページに開示情報はありませんでした。")
                break
            print(f"{len(rows)}件の情報を処理します...")
            for row in rows:
                cells = row.find_all('td')
                if len(cells) < 5: continue
                time_str, code_str, company_name, title = [cells[i].get_text(strip=True) for i in range(4)]
                if (company_name.startswith(('Ｅ－', 'Ｐ－', 'Ｒ－'))):
                    print(f"  -> スキップ (除外-社名): {company_name}")
                    continue
                title_upper = title.upper()
                if ('上場投信' in title or 'ＥＴＦ' in title_upper or 'ETF' in title_upper or '上場ETN' in title or '訂正' in title):
                    print(f"  -> スキップ (除外-表題): {title}")
                    continue
                link_tag = cells[3].find('a', href=True)
                if not link_tag: continue
                pdf_full_url = urljoin(content_url, link_tag['href'])
                all_pdf_links.append({"url": pdf_full_url, "date": date_str, "time": time_str.replace(':', ''), "code": code_str, "name": company_name, "title": title})
            page_num += 1
            time.sleep(0.5)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                if page_num > 1: print("次のページは見つかりませんでした。情報の取得を完了します。")
                else: print("開示情報ページが見つかりませんでした。")
            else: print(f"HTTPエラー: {e}")
            break
        except Exception as e:
            print(f"予期せぬエラー: {e}")
            break
    return all_pdf_links

def download_files(pdf_links, target_date):
    """取得したリンクからファイルをダウンロードする"""
    if not pdf_links:
        print("\nダウンロード対象のPDFが見つかりませんでした。")
        return
    save_dir = target_date.strftime('%y%m%d')
    print(f"\n合計 {len(pdf_links)}件のファイルをフォルダ '{save_dir}' にダウンロードします。")
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
        print(f"保存フォルダ '{save_dir}' を作成しました。")
    for i, item in enumerate(pdf_links):
        safe_name = item['name'][:50]
        safe_title = item['title'][:80]
        filename_base = f"{item['date']}{item['time']}_{item['code']}_{safe_name}_{safe_title}"
        filename = sanitize_filename(filename_base) + ".pdf"
        save_path = os.path.join(save_dir, filename)
        print(f"[{i+1}/{len(pdf_links)}] DL: {filename}")
        if not os.path.exists(save_path):
            try:
                pdf_response = requests.get(item['url'], headers=HEADERS, timeout=30)
                pdf_response.raise_for_status()
                with open(save_path, 'wb') as f:
                    f.write(pdf_response.content)
                time.sleep(0.5)
            except requests.RequestException as e:
                print(f"  -> ダウンロード失敗: {filename} ({e})")
        else:
            print(f"  -> スキップ (既存ファイル)")
    print("\n全ての処理が完了しました。")

def main():
    """メイン処理（自動実行用）"""
    print("TDnet Downloader (自動実行モード) を起動します。")
    JST = timezone(timedelta(hours=+9), 'JST')
    target_date = datetime.now(JST)
    print(f"本日 ({target_date.strftime('%Y年%m月%d日')}) のデータを取得します。")
    links = get_disclosure_links(target_date)
    download_files(links, target_date)

if __name__ == "__main__":
    main()
