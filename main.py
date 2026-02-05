import os
import sys
import time
import json
import re
import cloudscraper
import requests.cookies
import zipfile
import rarfile
import inquirer
import img2pdf
import shutil
import tempfile
from pathlib import Path
from PIL import Image
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from webdriver_manager.firefox import GeckoDriverManager
from urllib.parse import urljoin, urlparse, quote

# --- Цвета и Стили ---
CYAN = '\033[96m'
YELLOW = '\033[93m'
GREY = '\033[90m'
MAGENTA_BG = '\033[45m'
BLACK_FG = '\033[30m'
BOLD = '\033[1m'
RED = '\033[91m'
GREEN = '\033[92m'
ENDC = '\033[0m'
SEPARATOR = f"\n{GREY}────────────────────────────────────────────────────────────{ENDC}"

def clear_console():
    # Use ANSI escape codes for better compatibility with inquirer
    # \033[2J - Clear entire screen
    # \033[H - Move cursor to home position (top-left)
    if os.name == 'nt':
        os.system('cls')
    else:
        print('\033[2J\033[H', end='', flush=True)

def print_menu():
    title = f"{MAGENTA_BG}{BLACK_FG}{BOLD} COM-X.LIFE Downloader{ENDC}"
    author = f"{BOLD}Автор: https://github.com/smutchev{ENDC}"
    print(f"\n{title}  {author}\n")

class ComXLifeDownloader:
    def __init__(self, browser_choice='chrome', debug=False):
        self.debug = debug
        self.base_url = "https://com-x.life"
        self.session = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False},
            delay=1
        )
        self.cookies = {}
        self.browser_choice = browser_choice
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': self.base_url
        }

    def get_cookies_via_selenium(self):
        print(SEPARATOR)
        print("АВТОРИЗАЦИЯ")
        driver = None
        browser_name_display = self.browser_choice.capitalize()
        try:
            if self.browser_choice == 'chrome':
                chrome_options = ChromeOptions()
                chrome_options.add_argument("--disable-blink-features=AutomationControlled")
                chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
                chrome_options.add_experimental_option('useAutomationExtension', False)
                service = ChromeService(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=chrome_options)
            elif self.browser_choice == 'firefox':
                ff_options = FirefoxOptions()
                ff_options.set_preference("dom.webdriver.enabled", False)
                ff_options.set_preference('useAutomationExtension', False)
                ff_options.set_preference("general.useragent.override", self.headers['User-Agent'])
                service = FirefoxService(GeckoDriverManager().install())
                driver = webdriver.Firefox(service=service, options=ff_options)
            else:
                 print(f"✗ Неподдерживаемый браузер: {self.browser_choice}")
                 return False
        except Exception as e:
            print(f"✗ Ошибка запуска {browser_name_display}: {e}")
            print(f"\nПопробуйте установить {browser_name_display} или проверьте { 'ChromeDriver' if self.browser_choice == 'chrome' else 'GeckoDriver' }")
            return False
        if not driver:
             print("✗ Не удалось инициализировать драйвер")
             return False
        try:
            driver.get(self.base_url)
            print(f"\n⚠ Сейчас {browser_name_display} открыт")
            print("📝 Войдите в свой аккаунт на сайте com-x.life")
            print("⏳ Скрипт *автоматически* продолжит работу после обнаружения входа...")
            while True:
                try:
                    _ = driver.current_url
                    if driver.get_cookie("dle_user_id"):
                        print("\n✓ Обнаружен вход! Получаем cookies...")
                        cookies_list = driver.get_cookies()
                        for cookie in cookies_list:
                            self.cookies[cookie['name']] = cookie['value']
                        # Create a new cookie jar to completely replace session cookies (avoids duplicates)
                        new_jar = requests.cookies.RequestsCookieJar()
                        for name, value in self.cookies.items():
                            new_jar.set(name, value, domain='com-x.life')
                        self.session.cookies = new_jar
                        if self.cookies:
                            self.save_cookies()
                            print(f"✓ Получено {len(self.cookies)} cookies\n")
                            return True
                        else:
                            print("✗ Не удалось извлечь cookies, хотя вход был обнаружен.")
                            return False
                    time.sleep(1)
                except Exception:
                    print("\n✗ Браузер был закрыт пользователем до завершения авторизации.")
                    return False
        except Exception as e:
            print(f"✗ Ошибка во время ожидания авторизации: {e}")
            return False
        finally:
            try:
                driver.quit()
            except Exception:
                pass
        return False

    def save_cookies(self):
        cookies_file = Path('comx_cookies.json')
        with open(cookies_file, 'w', encoding='utf-8') as f:
            json.dump(self.cookies, f)
        print(f"✓ Cookies сохранены в {cookies_file}")

    def load_cookies(self):
        cookies_file = Path('comx_cookies.json')
        if cookies_file.exists():
            try:
                with open(cookies_file, 'r', encoding='utf-8') as f:
                    self.cookies = json.load(f)
                    # Create a new cookie jar to completely replace session cookies (avoids duplicates)
                    new_jar = requests.cookies.RequestsCookieJar()
                    for name, value in self.cookies.items():
                        new_jar.set(name, value, domain='com-x.life')
                    self.session.cookies = new_jar
                print("✓ Cookies загружены из файла")
                return True
            except Exception:
                pass
        return False

    def get_manga_id_from_url(self, url):
        match = re.search(r'/(\d+)-', url)
        if match:
            return match.group(1)
        return None

    def _perform_search_page(self, query, page=1):
        try:
            encoded_query = quote(query)
            search_url = f"{self.base_url}/search/{encoded_query}/page/{page}/" if page > 1 else f"{self.base_url}/search/{encoded_query}"
            response = self.session.get(search_url, headers=self.headers)
            if response.status_code != 200:
                return []
            soup = BeautifulSoup(response.content, 'lxml')
            content = soup.find('div', id='dle-content')
            if not content:
                return []
            results = []
            title_tags = content.find_all('h3', class_='readed__title')
            if not title_tags:
                return []
            for title_tag in title_tags:
                if title_tag.a:
                    title = title_tag.a.text.strip()
                    url = title_tag.a['href']
                    if not url.startswith('http'):
                        url = urljoin(self.base_url, url)
                    results.append({'title': title, 'url': url})
            return results
        except Exception:
            return []

    def fetch_search_results_sync(self, query):
        all_results = []
        current_page = 1
        limit = 30
        while len(all_results) < limit:
            page_results = self._perform_search_page(query, page=current_page)
            if not page_results:
                break
            all_results.extend(page_results)
            current_page += 1
        return all_results[:limit]

    def get_chapters_list(self, manga_url):
        print(SEPARATOR)
        print("ПОЛУЧЕНИЕ СПИСКА ГЛАВ")
        clean_url = manga_url.split('#')[0]
        response = self.session.get(clean_url, headers=self.headers)
        if response.status_code != 200:
            print(f"✗ Ошибка при загрузке страницы: {response.status_code}")
            if "Just a moment..." in response.text or response.status_code == 403:
                 print("✗ Похоже на защиту Cloudflare или бан. Попробуйте удалить comx_cookies.json и авторизоваться заново.")
            return None, None
        soup = BeautifulSoup(response.content, 'lxml')
        script_data = None
        for script in soup.find_all('script'):
            if script.string and 'window.__DATA__' in script.string:
                script_data = script.string
                break
        if not script_data:
            print("✗ Не удалось найти данные о главах (window.__DATA__)")
            return None, None
        try:
            json_match = re.search(r'window\.__DATA__\s*=\s*({.+?});', script_data, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(1))
                chapters = data.get('chapters', [])
                chapters.sort(key=lambda x: x.get('posi', 0))
                manga_title_raw = data.get("title", "Unknown Manga")
                manga_title = self.sanitize_filename(manga_title_raw)
                print(f"✓ Найдено глав: {len(chapters)}")
                print(f"✓ Название манги: {manga_title}\n")
                return chapters, manga_title
        except Exception as e:
            print(f"✗ Ошибка парсинга данных: {e}")
        return None, None

    def download_chapter(self, chapter, base_manga_folder, news_id, manga_url):
        start_time = time.time()
        chapter_id = chapter['id']
        chapter_title_raw = chapter.get('title', f"Глава {chapter.get('number', '?')}")
        chapter_posi = chapter.get('posi', 0)

        match = re.match(r'^\s*([\d\.]+)\s*-\s*([\d\.]+)\s*(.*)', chapter_title_raw)
        if match:
            vol = match.group(1).strip()
            ch = match.group(2).strip()
            title = match.group(3).strip()
            chapter_name = f"Vol. {vol} Ch. {ch} - {title}"
        else:
            chapter_name = f"Ch. {chapter_posi:03d} - {chapter_title_raw}"

        chapter_title_safe = self.sanitize_filename(chapter_name)
        chapter_folder = base_manga_folder / chapter_title_safe

        if chapter_folder.exists() and any(f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp'] for f in chapter_folder.iterdir()):
            print(f"  ⊘ {chapter_title_safe} (пропущено)")
            return True

        chapter_folder.mkdir(parents=True, exist_ok=True)
        temp_archive_path = None

        # ========================================================================
        # === ИЗМЕНЕНИЕ (v5.9): Убран Spinner ===
        # ========================================================================
        if self.debug:
            print(f"  🔗 Скачиваю: {chapter_title_safe}...")
        else:
            print(f"  🔗 Скачиваю: {chapter_title_safe}...", end="", flush=True)

        try:
            api_url = f"{self.base_url}/engine/ajax/controller.php?mod=api&action=chapters/download"
            payload = f"chapter_id={chapter_id}&news_id={news_id}"
            api_headers = self.headers.copy()
            api_headers.update({
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Referer": manga_url,
                "X-Requested-With": "XMLHttpRequest",
                "Origin": self.base_url
            })

            link_resp = self.session.post(api_url, headers=api_headers, data=payload)

            if link_resp.status_code != 200:
                time_taken_s = f"({time.time() - start_time:.2f} сек)"
                if self.debug:
                    print(f"  ✗ Ошибка API: {link_resp.status_code} для [#{chapter_posi}] {time_taken_s}")
                else:
                    print(f"\r  ✗ Ошибка API: {link_resp.status_code} для [#{chapter_posi}] {time_taken_s}")
                return False

            json_data = link_resp.json()
            raw_url = json_data.get("data")

            if not raw_url:
                time_taken_s = f"({time.time() - start_time:.2f} сек)"
                if self.debug:
                    print(f"  ✗ API не вернул ссылку для [#{chapter_posi}] (error: {json_data.get('error')}) {time_taken_s}")
                else:
                    print(f"\r  ✗ API не вернул ссылку для [#{chapter_posi}] (error: {json_data.get('error')}) {time_taken_s}")
                return False

            download_url = "https:" + raw_url.replace("\\/", "/")

            # if self.debug:
            #     print(f"  [DEBUG] API response: {json_data}")
            #     print(f"  [DEBUG] Download URL: {download_url}")

            parsed_url = urlparse(download_url)
            ext = Path(parsed_url.path).suffix
            if ext not in ['.zip', '.cbr']:
                ext = '.cbr'
            temp_archive_path = chapter_folder / f"__archive__{ext}"

            download_headers = self.headers.copy()
            download_headers['Referer'] = manga_url
            archive_response = self.session.get(download_url, headers=download_headers, stream=True, timeout=60)

            # if self.debug:
            #     print(f"  [DEBUG] Request headers: {dict(archive_response.request.headers)}")
            #     print(f"  [DEBUG] Response status: {archive_response.status_code}")
            #     print(f"  [DEBUG] Response headers: {dict(archive_response.headers)}")
            #     print(f"  [DEBUG] Session cookies: {dict(self.session.cookies)}")

            if archive_response.status_code == 200:
                with open(temp_archive_path, 'wb') as f:
                    for chunk in archive_response.iter_content(chunk_size=8192):
                        f.write(chunk)

                extracted = False
                try:
                    with zipfile.ZipFile(temp_archive_path, 'r') as zf:
                        zf.extractall(chapter_folder)
                    extracted = True
                except (zipfile.BadZipFile, zipfile.LargeZipFile):
                    try:
                        with rarfile.RarFile(temp_archive_path, 'r') as rf:
                            rf.extractall(chapter_folder)
                        extracted = True
                    except Exception:
                        time_taken_s = f"({time.time() - start_time:.2f} сек)"
                        if self.debug:
                            print(f"  ✗ Ошибка распаковки: {chapter_title_safe} (не ZIP и не RAR) {time_taken_s}")
                        else:
                            print(f"\r  ✗ Ошибка распаковки: {chapter_title_safe} (не ZIP и не RAR) {time_taken_s}")
                        return False
                except Exception:
                    time_taken_s = f"({time.time() - start_time:.2f} сек)"
                    if self.debug:
                        print(f"  ✗ Ошибка распаковки (ZIP): {chapter_title_safe} {time_taken_s}")
                    else:
                        print(f"\r  ✗ Ошибка распаковки (ZIP): {chapter_title_safe} {time_taken_s}")
                    return False
                finally:
                    if temp_archive_path.exists():
                        try:
                            temp_archive_path.unlink()
                        except Exception:
                            pass

                time_taken_s = f"({time.time() - start_time:.2f} сек)"
                # Перезаписываем строку "Скачиваю..."
                if self.debug:
                    print(f"  ✓ {chapter_title_safe} {time_taken_s}")
                else:
                    print(f"\r  ✓ {chapter_title_safe} {time_taken_s}{' ' * 20}")
                return extracted
            else:
                time_taken_s = f"({time.time() - start_time:.2f} сек)"
                if self.debug:
                    print(f"  ✗ Ошибка скачивания файла: {archive_response.status_code} {time_taken_s}")
                else:
                    print(f"\r  ✗ Ошибка скачивания файла: {archive_response.status_code} {time_taken_s}")
                return False

        except Exception as e:
            time_taken_s = f"({time.time() - start_time:.2f} сек)"
            if self.debug:
                print(f"  ✗ Критическая ошибка: {chapter_title_safe} ({e}) {time_taken_s}")
            else:
                print(f"\r  ✗ Критическая ошибка: {chapter_title_safe} ({e}) {time_taken_s}")
            if temp_archive_path and temp_archive_path.exists():
                try:
                    temp_archive_path.unlink()
                except Exception:
                    pass
            return False

    def download_manga(self, manga_url, output_dir="manga", start_chapter=None, end_chapter=None):
        if not self.load_cookies():
            if not self.get_cookies_via_selenium():
                print(f"\n{RED}✗ ОШИБКА: Не удалось авторизоваться{ENDC}")
                return False

        clear_console()
        print_menu()
        news_id = self.get_manga_id_from_url(manga_url)
        if not news_id:
            print(f"\n{RED}✗ Не удалось определить ID манги из URL{ENDC}")
            return False

        print(f"\n📖 ID манги: {news_id}")
        chapters, manga_title = self.get_chapters_list(manga_url)

        if not chapters or not manga_title:
            print(f"\n{RED}✗ Не удалось получить список глав или название манги{ENDC}")
            print("💡 Попробуйте:")
            print("    1. Удалить файл comx_cookies.json и авторизоваться заново")
            print("    2. Проверить правильность URL манги")
            return False

        if start_chapter or end_chapter:
            start = start_chapter or 1
            end = end_chapter or 99999
            chapters = [ch for ch in chapters if start <= ch.get('posi', 0) <= end]
            print(f"📌 Выбран диапазон: главы {start}-{end} ({len(chapters)} шт.)\n")

        base_manga_folder = Path(output_dir) / manga_title
        base_manga_folder.mkdir(parents=True, exist_ok=True)

        print(SEPARATOR)
        print(f"{CYAN}{BOLD}СКАЧИВАНИЕ ГЛАВ{ENDC}")
        print(SEPARATOR)

        total_start_time = time.time()
        success_count = 0

        for idx, chapter in enumerate(chapters, 1):
            try:
                if self.download_chapter(chapter, base_manga_folder, news_id, manga_url):
                    success_count += 1
                time.sleep(1)
            except KeyboardInterrupt:
                print(f"\n\n{YELLOW}⚠ Прервано пользователем{ENDC}")
                break
            except Exception as e:
                print(f"  {RED}✗ Ошибка: {e}{ENDC}")
                continue

        total_time_taken = time.time() - total_start_time

        print(SEPARATOR)
        print(f"{GREEN}{BOLD}ЗАВЕРШЕНО{ENDC}")
        print(SEPARATOR)
        print(f"✓ Успешно скачано: {success_count}/{len(chapters)} глав")
        print(f"🕒 Общее время: {total_time_taken:.2f} сек")
        print(f"📁 Сохранено в: {base_manga_folder.absolute()}\n")

        if success_count > 0:
            self.prompt_pdf_creation(base_manga_folder, manga_title)

        return True

    @staticmethod
    def sanitize_filename(filename):
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        filename = re.sub(r'[\s_]+', ' ', filename)
        return filename.strip()

    @staticmethod
    def parse_range(range_str):
        range_str = range_str.strip()
        if not range_str:
            return None, None
        if '-' in range_str:
            parts = range_str.split('-')
            try:
                start = int(parts[0]) if parts[0] else None
            except ValueError:
                start = None
            try:
                end = int(parts[1]) if parts[1] else None
            except ValueError:
                end = None
            return start, end
        else:
            try:
                num = int(range_str)
                return num, num
            except ValueError:
                return None, None

    @staticmethod
    def parse_chapter_sort_key(folder_name):
        """Extract volume/chapter numbers from folder name for sorting."""
        # Pattern: "Vol. X Ch. Y - Title"
        match = re.match(r'Vol\.\s*([\d.]+)\s*Ch\.\s*([\d.]+)', folder_name)
        if match:
            try:
                vol = float(match.group(1))
                ch = float(match.group(2))
                return (vol, ch)
            except ValueError:
                pass

        # Pattern: "Ch. X - Title"
        match = re.match(r'Ch\.\s*([\d.]+)', folder_name)
        if match:
            try:
                ch = float(match.group(1))
                return (0, ch)
            except ValueError:
                pass

        # Fallback: extract any number
        numbers = re.findall(r'[\d.]+', folder_name)
        if numbers:
            try:
                return (0, float(numbers[0]))
            except ValueError:
                pass

        return (0, 0)

    @staticmethod
    def get_sorted_chapter_folders(manga_folder):
        """Return chapter folders sorted by volume/chapter number."""
        folders = [f for f in manga_folder.iterdir() if f.is_dir()]
        folders.sort(key=lambda f: ComXLifeDownloader.parse_chapter_sort_key(f.name))
        return folders

    @staticmethod
    def get_sorted_images(chapter_folder):
        """Return image files sorted naturally (2.jpg before 10.jpg)."""
        image_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
        images = [f for f in chapter_folder.iterdir()
                  if f.is_file() and f.suffix.lower() in image_extensions]

        def natural_sort_key(path):
            # Extract numbers for natural sorting
            parts = re.split(r'(\d+)', path.stem)
            return [int(p) if p.isdigit() else p.lower() for p in parts]

        images.sort(key=natural_sort_key)
        return images

    @staticmethod
    def convert_webp_to_jpeg(webp_path, temp_dir):
        """Convert WebP image to JPEG for img2pdf compatibility."""
        try:
            img = Image.open(webp_path)
            # Handle RGBA/alpha channel
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            jpeg_path = Path(temp_dir) / f"{webp_path.stem}.jpg"
            img.save(jpeg_path, 'JPEG', quality=95)
            return jpeg_path
        except Exception as e:
            print(f"    {YELLOW}⚠ Не удалось конвертировать {webp_path.name}: {e}{ENDC}")
            return None

    def create_pdf(self, manga_folder, output_pdf_path):
        """Create PDF from all chapter images."""
        print(f"\n{CYAN}📄 Создание PDF...{ENDC}")

        chapter_folders = self.get_sorted_chapter_folders(manga_folder)
        if not chapter_folders:
            print(f"{RED}✗ Не найдено папок с главами{ENDC}")
            return False

        all_images = []
        temp_dir = None

        try:
            # Collect all images
            for folder in chapter_folders:
                images = self.get_sorted_images(folder)
                if not images:
                    print(f"  {YELLOW}⚠ Пустая папка: {folder.name}{ENDC}")
                    continue
                all_images.extend(images)

            if not all_images:
                print(f"{RED}✗ Не найдено изображений для PDF{ENDC}")
                return False

            print(f"  Найдено {len(all_images)} изображений в {len(chapter_folders)} главах")

            # Process images (convert WebP if needed)
            temp_dir = tempfile.mkdtemp()
            image_paths = []

            for idx, img_path in enumerate(all_images):
                # Show progress
                progress = (idx + 1) / len(all_images) * 100
                print(f"\r  Обработка: {progress:.0f}%", end="", flush=True)

                if img_path.suffix.lower() == '.webp':
                    converted = self.convert_webp_to_jpeg(img_path, temp_dir)
                    if converted:
                        image_paths.append(str(converted))
                else:
                    image_paths.append(str(img_path))

            print("\r  Обработка: 100%   ")

            if not image_paths:
                print(f"{RED}✗ Нет изображений для включения в PDF{ENDC}")
                return False

            # Create PDF
            print("  Генерация PDF...")
            with open(output_pdf_path, 'wb') as f:
                f.write(img2pdf.convert(image_paths))

            # Report file size
            file_size = output_pdf_path.stat().st_size
            if file_size >= 1024 * 1024 * 1024:
                size_str = f"{file_size / (1024 * 1024 * 1024):.2f} ГБ"
            elif file_size >= 1024 * 1024:
                size_str = f"{file_size / (1024 * 1024):.2f} МБ"
            else:
                size_str = f"{file_size / 1024:.2f} КБ"

            print(f"{GREEN}✓ PDF создан: {output_pdf_path} ({size_str}){ENDC}")
            return True

        except KeyboardInterrupt:
            print(f"\n{YELLOW}⚠ Создание PDF прервано{ENDC}")
            if output_pdf_path.exists():
                output_pdf_path.unlink()
            return False
        except Exception as e:
            print(f"{RED}✗ Ошибка создания PDF: {e}{ENDC}")
            return False
        finally:
            # Clean up temp directory
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    def delete_manga_folder(self, manga_folder):
        """Delete the entire manga folder with all images."""
        try:
            shutil.rmtree(manga_folder)
            print(f"✓ Удалена папка: {manga_folder.name}")
        except Exception as e:
            print(f"  {YELLOW}⚠ Не удалось удалить {manga_folder.name}: {e}{ENDC}")

    def prompt_pdf_creation(self, manga_folder, manga_title):
        """Ask user if they want to create PDF and optionally delete originals."""
        try:
            questions = [
                inquirer.Confirm('create_pdf',
                                 message="📄 Создать PDF из всех глав?",
                                 default=True),
            ]
            answers = inquirer.prompt(questions)

            if not answers or not answers['create_pdf']:
                return

            # Create PDF in parent directory (e.g., Manga/Title.pdf instead of Manga/Title/Title.pdf)
            pdf_filename = f"{manga_title}.pdf"
            output_pdf_path = manga_folder.parent / pdf_filename

            if not self.create_pdf(manga_folder, output_pdf_path):
                return

            # Ask about deleting originals
            questions = [
                inquirer.Confirm('delete_originals',
                                 message="🗑  Удалить исходные изображения?",
                                 default=False),
            ]
            answers = inquirer.prompt(questions)

            if answers and answers['delete_originals']:
                self.delete_manga_folder(manga_folder)

        except KeyboardInterrupt:
            print(f"\n{YELLOW}⚠ Отменено{ENDC}")

def main():
    if sys.version_info < (3, 7):
        print(f"{RED}✗ Ошибка: Этот скрипт требует Python 3.7+.{ENDC}")
        sys.exit(1)

    clear_console()
    print_menu()

    try:
        questions = [
            inquirer.List('browser',
                          message="🔧 Выберите браузер для авторизации",
                          choices=['Chrome', 'Firefox'],
                          carousel=True),
        ]
        answers = inquirer.prompt(questions)
        if not answers:
            raise KeyboardInterrupt

        browser_name = answers['browser'].lower()
        downloader = ComXLifeDownloader(browser_choice=browser_name, debug=True)

        while True:
            clear_console()
            print_menu()

            questions = [
                inquirer.Text('query',
                              message="📖 Введите URL или Название манги (Enter для выхода)"),
            ]
            answers = inquirer.prompt(questions)

            if not answers or not answers['query']:
                raise KeyboardInterrupt

            input_str = answers['query'].strip()
            manga_url = None

            if 'com-x.life' in input_str and 'http' in input_str:
                manga_url = input_str
            else:
                clear_console()
                print_menu()
                print(f"\n{YELLOW}🔍 Ищу '{input_str}'...{ENDC}")
                results = downloader.fetch_search_results_sync(input_str)

                clear_console()
                print_menu()

                if not results:
                    print(f"{RED}✗ Ничего не найдено по запросу '{input_str}'.{ENDC}")
                    time.sleep(2)
                    continue

                if len(results) == 1:
                    manga_url = results[0]['url']
                    print(f"✓ Найдена 1 манга: {results[0]['title']}")
                else:
                    print(f"\n{YELLOW}📚 Найдено {len(results)} результатов. Выберите:{ENDC}")
                    for i, res in enumerate(results, 1):
                        print(f"  {i:02d}: {res['title']}")

                    print(f"\n{GREY}(Введите номер или нажмите Enter для нового поиска){ENDC}")
                    choice_str = input(f"{CYAN}Выберите номер: {ENDC}").strip()

                    if not choice_str:
                        continue

                    try:
                        choice_idx = int(choice_str) - 1
                        if 0 <= choice_idx < len(results):
                            manga_url = results[choice_idx]['url']
                            print(f"✓ Выбрано: {results[choice_idx]['title']}")
                        else:
                            print(f"{RED}✗ Неверный номер.{ENDC}")
                            time.sleep(2)
                            continue
                    except ValueError:
                        print(f"{RED}✗ Неверный ввод.{ENDC}")
                        time.sleep(2)
                        continue

            if not manga_url:
                 continue

            questions = [
                inquirer.Text('output',
                              message="📁 Папка для сохранения",
                              default='Manga'),
                inquirer.Text('range',
                              message="💡 Укажите диапазон (Enter = все)",
                              default=''),
            ]
            answers = inquirer.prompt(questions)

            if not answers:
                continue

            output_dir = answers['output'].strip() or 'manga'
            start_chapter, end_chapter = ComXLifeDownloader.parse_range(answers['range'])

            downloader.download_manga(manga_url, output_dir, start_chapter, end_chapter)

            print(f"\n{CYAN}Нажмите Enter, чтобы начать новый поиск...{ENDC}")
            input()

    except KeyboardInterrupt:
        print()
        sys.exit(0)
    except Exception as e:
        print(f"\n{RED}✗ Критическая ошибка: {e}{ENDC}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
