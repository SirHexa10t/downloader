import unittest


class DownloadCases(unittest.TestCase):

    def test_domain_finder(self):
        from downloader_main import get_domain
        # yes, this is ugly. But it's very verbose, and a more complicated check would have more room for errors
        assert 'example.com' == get_domain("https://www.example.com/path/to/resource")
        assert 'example.com' == get_domain("http://www.example.com/path/to/resource")
        assert 'example.com' == get_domain("https://example.com/path/to/resource")
        assert 'example.com' == get_domain("https://example.com/path/to/resource")
        assert 'example.com' == get_domain("www.example.com/path/to/resource")
        assert 'example.com' == get_domain("example.com/path/to/resource")
        assert 'example.com' == get_domain("https://www.example.com/")
        assert 'example.com' == get_domain("http://www.example.com/")
        assert 'example.com' == get_domain("https://example.com/")
        assert 'example.com' == get_domain("https://example.com/")
        assert 'example.com' == get_domain("www.example.com/")
        assert 'example.com' == get_domain("example.com/")
        assert 'example.com' == get_domain("https://www.example.com")
        assert 'example.com' == get_domain("http://www.example.com")
        assert 'example.com' == get_domain("https://example.com")
        assert 'example.com' == get_domain("https://example.com")
        assert 'example.com' == get_domain("www.example.com")
        assert 'example.com' == get_domain("example.com")
        assert get_domain("examplecom") is None
        assert get_domain("example . com") is None
        assert get_domain("") is None
