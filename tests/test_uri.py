import unittest
from simdb.uri import URI
from pathlib import Path

class URITests(unittest.TestCase):

    def test_empty_uri(self):
        uri = URI("imas:")
        self.assertEqual(uri.scheme, "imas")

    def test_uri_without_scheme_throws(self):
        with self.assertRaises(ValueError):
            _uri = URI()

    def test_uri_with_path(self):
        uri = URI("imas:hdf5")
        self.assertEqual(uri.path, Path("hdf5"))

    def test_uri_with_query(self):
        uri = URI("imas:hdf5?path=foo")
        self.assertIn("path", uri.query)
        self.assertEqual(uri.query["path"], "foo")

    def test_uri_with_authority(self):
        uri = URI("imas://uda.iter.org/hdf5?path=foo")
        self.assertEqual(uri.authority.host, "uda.iter.org")

    def test_uri_with_authority_with_port(self):
        uri = URI("imas://uda.iter.org:56565/hdf5?path=foo")
        self.assertEqual(uri.authority.port, 56565)

    def test_uri_with_authority_with_auth(self):
        uri = URI("imas://user:passwd@uda.iter.org/hdf5?path=foo")
        self.assertEqual(uri.authority.auth, 'user:passwd')

    def test_get_query_argument_with_default(self):
        uri = URI("imas:hdf5")
        self.assertNotIn("path", uri.query)
        self.assertEqual(uri.query.get("path", default="foo"), "foo")

    def test_updating_uri_query(self):
        uri = URI("imas:hdf5?path=foo")
        uri.query.set("path", "bar")
        self.assertIn("path", uri.query)
        self.assertEqual(uri.query["path"], "bar")

    def test_removing_argument_from_uri_query(self):
        uri = URI("imas:hdf5?path=foo")
        uri.query.remove("path")
        self.assertNotIn("path", uri.query)

    def test_uri_to_string_just_path(self):
        uri = URI("imas:hdf5")
        self.assertEqual(str(uri), "imas:hdf5")

    def test_uri_to_string_full_uri(self):
        uri = URI("imas://authority/hdf5?path=foo#frag")
        self.assertEqual(str(uri), "imas://authority/hdf5?path=foo#frag")

    def test_uri_with_empty_authority_to_string(self):
        uri = URI("imas:///hdf5?path=foo#frag")
        self.assertEqual(str(uri), "imas:hdf5?path=foo#frag")