import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin

# Alterado para importar o novo domínio
from common import ZLIB_DOMAIN


class BookInfo:
    """Classe para armazenar informações do livro (sem alterações)."""

    def __init__(self, book):
        self.id = book.get('id')
        self.title = book.get('title')
        self.authors = book.get('authors')
        self.publisher = book.get('publisher')  # Z-lib não fornece isso facilmente na busca
        self.year = book.get('year')
        self.pages = book.get('pages')  # Z-lib não fornece isso facilmente na busca
        self.language = book.get('language')
        self.size = book.get('size')
        self.format = book.get('format')
        self.download_links = book.get('links', [])

    def __repr__(self):
        return f'BookInfo(authors: {self.authors}, title: {self.title[:25]}...)'

    def __str__(self):
        return (
            f"<b>Título:</b> {self.title}\n"
            f"<b>Autor(es):</b> {self.authors}\n"
            f"<b>Ano:</b> {self.year}\n"
            f"<b>Idioma:</b> {self.language}\n"
            f"<b>Formato:</b> {self.format}\n"
            f"<b>Tamanho:</b> {self.size}"
        )


class BookInfoProvider:
    """Classe reescrita para carregar informações de livros do Z-Library."""
    BASE_URL = ZLIB_DOMAIN
    # A URL de busca do Z-Library é mais simples
    SEARCH_URL = BASE_URL + '/s/{query}'

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def load_book_list(self, search_query, search_type=''):  # search_type não é mais usado
        """Carrega uma lista de livros do Z-Library."""
        search_query_encoded = quote(search_query.strip())
        url = self.SEARCH_URL.format(query=search_query_encoded)

        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Erro ao acessar a URL de busca do Z-Library: {e}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        # Os livros estão em contêineres com a classe 'book-item-wrapper'
        book_items = soup.find_all('div', class_='book-item-wrapper', limit=10)

        if not book_items:
            return []

        book_list = []
        for item in book_items:
            try:
                book_data = self.__extract_book(item)
                if book_data and book_data.get('links'):
                    book_list.append(BookInfo(book_data))
            except Exception as e:
                print(f"Erro ao extrair dados do livro: {e}")
                continue

        return book_list

    def __extract_book(self, item):
        """Extrai informações de um item de livro da página de resultados."""
        # Encontra o link para a página do livro e o título
        title_tag = item.find('h3', class_='book-title').find('a')
        if not title_tag:
            return None

        book_page_relative_url = title_tag['href']
        # Constrói a URL absoluta para a página do livro
        book_page_url = urljoin(self.BASE_URL, book_page_relative_url)

        # Extrai os autores
        authors = ', '.join([a.text for a in item.find_all('div', class_='authors')])

        # Extrai detalhes como ano, idioma, formato e tamanho
        year_div = item.find('div', class_='property_year')
        year = year_div.find('div', class_='property_value').text.strip() if year_div else 'N/A'

        lang_div = item.find('div', class_='property_language')
        language = lang_div.find('div', class_='property_value').text.strip() if lang_div else 'N/A'

        file_info_div = item.find('div', class_='property_file')
        file_info_text = file_info_div.find('div',
                                            class_='property_value').text.strip() if file_info_div else 'N/A, N/A'

        file_format, file_size = [x.strip() for x in file_info_text.split(',')]

        book = {
            'id': book_page_relative_url.split('/')[2],  # Usa parte da URL como ID
            'title': title_tag.text.strip(),
            'authors': authors,
            'year': year,
            'language': language,
            'format': file_format,
            'size': file_size,
            'publisher': 'N/A',  # Não disponível na página de busca
            'pages': 'N/A',  # Não disponível na página de busca
            'links': []
        }

        # Agora, visita a página do livro para obter o link de download final
        final_download_link = self.__get_final_download_link(book_page_url)
        if final_download_link:
            book['links'].append(final_download_link)

        return book

    def __get_final_download_link(self, book_page_url):
        """Navega até a página do livro para obter o link de download final."""
        try:
            response = self.session.get(book_page_url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            # O link de download está em um botão com a classe 'btn-dl'
            download_button = soup.find('a', class_='btn-dl')

            if download_button and download_button.has_attr('href'):
                relative_link = download_button['href']
                # Constrói a URL de download absoluta
                return urljoin(self.BASE_URL, relative_link)

        except requests.RequestException as e:
            print(f"Erro ao acessar a página do livro {book_page_url}: {e}")

        return None