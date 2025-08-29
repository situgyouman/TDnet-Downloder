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

    while True: # 全てのページを巡回するためのループ
        try:
            content_url = f"https://www.release.tdnet.info/inbs/I_list_{page_num:03d}_{date_str}.html"
            
            print(f"[{page_num}ページ目] {content_url} にアクセスします...")
            response = requests.get(content_url, headers=HEADERS, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser', from_encoding='MS932')
            
            result_table = soup.find('table', id='main-list-table')
            if not result_table:
                if page_num == 1:
                    print("開示情報が見つかりませんでした。")
                else:
                    print("次のページは見つかりませんでした。情報の取得を完了します。")
                break

            rows = result_table.find_all('tr')
            if not rows:
                print("このページに開示情報はありませんでした。")
                break
            
            print(f"{len(rows)}件の情報を処理します...")

            for row in rows:
                cells = row.find_all('td')
                if len(cells) < 5: continue

                time_str = cells[0].get_text(strip=True)
                code_str = cells[1].get_text(strip=True)
                company_name = cells[2].get_text(strip=True)
                title = cells[3].get_text(strip=True)
                
                # 除外条件のチェック
                if (company_name.startswith('Ｅ－') or 
                    company_name.startswith('Ｐ－') or 
                    company_name.startswith('Ｒ－')):
                    print(f"  -> スキップ (除外-社名): {company_name}")
                    continue
                
                title_upper = title.upper()
                if ('上場投信' in title or 
                    'ＥＴＦ' in title_upper or 'ETF' in title_upper or 
                    '上場ETN' in title or 
                    '訂正' in title):
                    print(f"  -> スキップ (除外-表題): {title}")
                    continue
                
                link_tag = cells[3].find('a')
                if not link_tag or not link_tag.has_attr('href'): continue

                pdf_relative_url = link_tag['href']
                pdf_full_url = urljoin(content_url, pdf_relative_url)
                
                all_pdf_links.append({
                    "url": pdf_full_url,
                    "date": date_str,
                    "time": time_str.replace(':', ''),
                    "code": code_str,
                    "name": company_name,
                    "title": title,
                })
            
            page_num += 1
            time.sleep(0.5)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                if page_num == 1:
                    print("開示情報ページが見つかりませんでした。")
                else:
                    print("次のページは見つかりませんでした。情報の取得を完了します。")
                break
            else:
                print(f"HTTPリクエスト中にエラーが発生しました: {e}")
                break
        except Exception as e:
            print(f"処理中に予期せぬエラーが発生しました: {e}")
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

    total_count = len(pdf_links)
    for i, item in enumerate(pdf_links):
        # ▼▼▼ 変更点：ファイル名の表題部分が長すぎる場合に省略する ▼▼▼
        title_for_filename = (item['title'][:100] + '…') if len(item['title']) > 100 else item['title']
        
        filename = sanitize_filename(f"{item['date']}{item['time']}_{item['code']}_{item['name']}_{title_for_filename}.pdf")
        save_path = os.path.join(save_dir, filename)
        
        print(f"[{i+1}/{total_count}] DL: {filename}")

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
    
    # 日本標準時(JST)の現在時刻を取得
    JST = timezone(timedelta(hours=+9), 'JST')
    target_date = datetime.now(JST)
    
    print(f"本日 ({target_date.strftime('%Y年%m月%d日')}) のデータを取得します。")

    links = get_disclosure_links(target_date)
    download_files(links, target_date)

if __name__ == "__main__":
    main()
