"""更新済みの私有AWS Demoを本機のSSHトンネル経由で検証し、実画面を撮影する。"""
import argparse
import re
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = 'http://127.0.0.1:8000/'


def capture(updated: bool) -> None:
    """aws-v2更新確認後のみ実行し、両方の回答が正しい場合だけ成果物を保存する。"""
    if not updated:
        raise SystemExit('先にEC2のaws-v2更新を確認してください。確認後に --aws-v2-confirmed を指定します。')
    from playwright.sync_api import sync_playwright

    with tempfile.TemporaryDirectory(prefix='verified-demo-') as temporary:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                context = browser.new_context(viewport={'width': 1440, 'height': 1100}, device_scale_factor=1)
                page = context.new_page()
                page.set_default_timeout(60000)
                page.goto(URL, wait_until='networkidle', timeout=15000)
                if page.locator('html').get_attribute('lang') != 'ja':
                    raise RuntimeError('日語UIを確認できません。旧イメージまたは別サービスの可能性があります。')
                page.get_by_role('heading', name='社内規定・業務データの照会').wait_for()
                # 架空のseedユーザーのみ使用。アップロード・申請・seedは行わない。
                page.locator('#user-id').fill('U001')
                page.locator('#department-id').fill('D-SALES')
                page.locator('#role-ids').fill('EMPLOYEE,ADMIN')
                balance = context.request.get(URL + 'api/me/leave-balance', headers={'X-User-Id': 'U001'})
                if balance.status != 200:
                    raise RuntimeError('本人の残日数データを取得できません。')
                days = balance.json()['remaining_days']
                cases = [
                    ('rag-query.png', '国内出張の宿泊費上限はいくらですか？'),
                    ('leave-balance.png', '私の有給休暇はあと何日ありますか？'),
                ]
                for case in cases:
                    filename = case[0]
                    question = case[1]
                    page.goto(URL, wait_until='networkidle')
                    page.locator('#user-id').fill('U001')
                    page.locator('#department-id').fill('D-SALES')
                    page.locator('#role-ids').fill('EMPLOYEE,ADMIN')
                    page.locator('#message').fill(question)
                    with page.expect_response(lambda response: response.url == URL + 'api/chat' and response.request.method == 'POST') as pending:
                        page.locator('#send-button').click()
                    response = pending.value
                    if response.status != 200:
                        raise RuntimeError('チャット照会に失敗しました。')
                    result = response.json()
                    if filename == 'rag-query.png':
                        citation_found = False
                        sources = result.get('sources', [])
                        for source in sources:
                            if source.get('source_name') == 'TravelPolicy_v1.pdf' and source.get('page') == 3:
                                citation_found = True
                        answer = result['answer']
                        amount_found = re.search(r'10[,，]?000|1万', answer)
                        japanese_found = re.search(r'[ぁ-んァ-ヶ]', answer)
                        valid = (result.get('intent') == 'knowledge_query'
                                 and result.get('evidence_found')
                                 and amount_found
                                 and '円' in answer
                                 and japanese_found
                                 and citation_found)
                    else:
                        leave_balance = result.get('leave_balance', {})
                        valid = (result.get('intent') == 'leave_balance'
                                 and leave_balance.get('remaining_days') == days
                                 and result['answer'] == f'有給休暇の残日数は{days:g}日です。')
                    if not valid:
                        raise RuntimeError(f'{filename}: 想定する日本語回答・出典を検証できません。画像は保存しません。')
                    page.locator('.assistant-message').last.wait_for()
                    page.wait_for_function("!document.querySelector('#send-button').disabled")
                    page.evaluate("document.querySelector('#chat-feed').scrollTop = 0")
                    complete_chat = page.locator('#chat-feed').evaluate('(element) => element.scrollHeight <= element.clientHeight + 1')
                    if not complete_chat:
                        raise RuntimeError('問答がスクロール領域に収まりません。画像は保存しません。')
                    print(f'{filename}: {result}', flush=True)
                    page.screenshot(path=str(Path(temporary) / filename), full_page=True)
                output = ROOT / 'docs/images'
                output.mkdir(parents=True, exist_ok=True)
                for case in cases:
                    filename = case[0]
                    temporary_path = Path(temporary) / filename
                    image_bytes = temporary_path.read_bytes()
                    output_path = output / filename
                    output_path.write_bytes(image_bytes)
                readme = ROOT / 'README.md'
                text = readme.read_text(encoding='utf-8')
                marker = '<!-- VERIFIED_DEMO_SCREENSHOTS -->'
                if marker in text:
                    text = text.replace(marker, '''### 実際のDemo画面

架空データを使用した私有Demoの実画面です。日語の回答と出典・残日数を検証後に撮影しています。

**社内文書への質問と出典確認**

![国内出張の宿泊費照会とPDFの出典](docs/images/rag-query.png)

**本人の有給休暇残日数照会**

![有給休暇の残日数照会](docs/images/leave-balance.png)''')
                    readme.write_text(text, encoding='utf-8')
                print('検証成功：2枚の実画面PNGを保存しました。公開前に画像を目視確認してください。')
            finally:
                browser.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aws-v2-confirmed', action='store_true')
    arguments = parser.parse_args()
    capture(arguments.aws_v2_confirmed)
