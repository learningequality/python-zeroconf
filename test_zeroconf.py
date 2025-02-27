#!/usr/bin/env python
# -*- coding: utf-8 -*-


""" Unit tests for zeroconf.py """

import copy
import logging
import socket
import struct
import time
import unittest
from threading import Event

from six import indexbytes
from six.moves import xrange

import zeroconf as r
from zeroconf import (
    DNSHinfo,
    DNSText,
    ServiceBrowser,
    ServiceInfo,
    ServiceStateChange,
    Zeroconf,
    ZeroconfServiceTypes,
)

log = logging.getLogger("zeroconf")
original_logging_level = [None]


def setup_module():
    original_logging_level[0] = log.level
    log.setLevel(logging.DEBUG)


def teardown_module():
    log.setLevel(original_logging_level[0])


class TestDunder(unittest.TestCase):
    def test_dns_text_repr(self):
        # There was an issue on Python 3 that prevented DNSText's repr
        # from working when the text was longer than 10 bytes
        text = DNSText("irrelevant", None, 0, 0, b"12345678901")
        repr(text)

        text = DNSText("irrelevant", None, 0, 0, b"123")
        repr(text)

    def test_dns_hinfo_repr_eq(self):
        hinfo = DNSHinfo("irrelevant", r._TYPE_HINFO, 0, 0, "cpu", "os")
        assert hinfo == hinfo
        repr(hinfo)

    def test_dns_pointer_repr(self):
        pointer = r.DNSPointer(
            "irrelevant", r._TYPE_PTR, r._CLASS_IN, r._DNS_TTL, "123"
        )
        repr(pointer)

    def test_dns_address_repr(self):
        address = r.DNSAddress("irrelevant", r._TYPE_SOA, r._CLASS_IN, 1, b"a")
        repr(address)

    def test_dns_question_repr(self):
        question = r.DNSQuestion(
            "irrelevant", r._TYPE_SRV, r._CLASS_IN | r._CLASS_UNIQUE
        )
        repr(question)
        assert not question != question

    def test_dns_service_repr(self):
        service = r.DNSService(
            "irrelevant", r._TYPE_SRV, r._CLASS_IN, r._DNS_TTL, 0, 0, 80, b"a"
        )
        repr(service)

    def test_dns_record_abc(self):
        record = r.DNSRecord("irrelevant", r._TYPE_SRV, r._CLASS_IN, r._DNS_TTL)
        self.assertRaises(r.AbstractMethodException, record.__eq__, record)
        self.assertRaises(r.AbstractMethodException, record.write, None)

    def test_service_info_dunder(self):
        type_ = "_test-srvc-type._tcp.local."
        name = "xxxyyy"
        registration_name = "%s.%s" % (name, type_)
        info = ServiceInfo(
            type_,
            registration_name,
            socket.inet_aton("10.0.1.2"),
            80,
            0,
            0,
            None,
            "ash-2.local.",
        )

        assert not info != info
        repr(info)

    def test_dns_outgoing_repr(self):
        dns_outgoing = r.DNSOutgoing(r._FLAGS_QR_QUERY)
        repr(dns_outgoing)


class PacketGeneration(unittest.TestCase):
    def test_parse_own_packet_simple(self):
        generated = r.DNSOutgoing(0)
        r.DNSIncoming(generated.packet())

    def test_parse_own_packet_simple_unicast(self):
        generated = r.DNSOutgoing(0, 0)
        r.DNSIncoming(generated.packet())

    def test_parse_own_packet_flags(self):
        generated = r.DNSOutgoing(r._FLAGS_QR_QUERY)
        r.DNSIncoming(generated.packet())

    def test_parse_own_packet_question(self):
        generated = r.DNSOutgoing(r._FLAGS_QR_QUERY)
        generated.add_question(
            r.DNSQuestion("testname.local.", r._TYPE_SRV, r._CLASS_IN)
        )
        r.DNSIncoming(generated.packet())

    def test_parse_own_packet_response(self):
        generated = r.DNSOutgoing(r._FLAGS_QR_RESPONSE)
        generated.add_answer_at_time(
            r.DNSService(
                u"æøå.local.",
                r._TYPE_SRV,
                r._CLASS_IN,
                r._DNS_TTL,
                0,
                0,
                80,
                u"foo.local.",
            ),
            0,
        )
        parsed = r.DNSIncoming(generated.packet())
        self.assertEqual(len(generated.answers), 1)
        self.assertEqual(len(generated.answers), len(parsed.answers))

    def test_match_question(self):
        generated = r.DNSOutgoing(r._FLAGS_QR_QUERY)
        question = r.DNSQuestion("testname.local.", r._TYPE_SRV, r._CLASS_IN)
        generated.add_question(question)
        parsed = r.DNSIncoming(generated.packet())
        self.assertEqual(len(generated.questions), 1)
        self.assertEqual(len(generated.questions), len(parsed.questions))
        self.assertEqual(question, parsed.questions[0])

    def test_suppress_answer(self):
        query_generated = r.DNSOutgoing(r._FLAGS_QR_QUERY)
        question = r.DNSQuestion("testname.local.", r._TYPE_SRV, r._CLASS_IN)
        query_generated.add_question(question)
        answer1 = r.DNSService(
            "testname1.local.",
            r._TYPE_SRV,
            r._CLASS_IN,
            r._DNS_TTL,
            0,
            0,
            80,
            "foo.local.",
        )
        staleanswer2 = r.DNSService(
            "testname2.local.",
            r._TYPE_SRV,
            r._CLASS_IN,
            r._DNS_TTL / 2,
            0,
            0,
            80,
            "foo.local.",
        )
        answer2 = r.DNSService(
            "testname2.local.",
            r._TYPE_SRV,
            r._CLASS_IN,
            r._DNS_TTL,
            0,
            0,
            80,
            "foo.local.",
        )
        query_generated.add_answer_at_time(answer1, 0)
        query_generated.add_answer_at_time(staleanswer2, 0)
        query = r.DNSIncoming(query_generated.packet())

        # Should be suppressed
        response = r.DNSOutgoing(r._FLAGS_QR_RESPONSE)
        response.add_answer(query, answer1)
        assert len(response.answers) == 0

        # Should not be suppressed, TTL in query is too short
        response.add_answer(query, answer2)
        assert len(response.answers) == 1

        # Should not be suppressed, name is different
        tmp = copy.copy(answer1)
        tmp.name = "testname3.local."
        response.add_answer(query, tmp)
        assert len(response.answers) == 2

        # Should not be suppressed, type is different
        tmp = copy.copy(answer1)
        tmp.type = r._TYPE_A
        response.add_answer(query, tmp)
        assert len(response.answers) == 3

        # Should not be suppressed, class is different
        tmp = copy.copy(answer1)
        tmp.class_ = r._CLASS_NONE
        response.add_answer(query, tmp)
        assert len(response.answers) == 4

        # ::TODO:: could add additional tests for DNSAddress, DNSHinfo, DNSPointer, DNSText, DNSService

    def test_dns_hinfo(self):
        generated = r.DNSOutgoing(0)
        generated.add_additional_answer(
            DNSHinfo("irrelevant", r._TYPE_HINFO, 0, 0, "cpu", "os")
        )
        parsed = r.DNSIncoming(generated.packet())
        self.assertEqual(parsed.answers[0].cpu, u"cpu")
        self.assertEqual(parsed.answers[0].os, u"os")

        generated = r.DNSOutgoing(0)
        generated.add_additional_answer(
            DNSHinfo("irrelevant", r._TYPE_HINFO, 0, 0, "cpu", "x" * 257)
        )
        self.assertRaises(r.NamePartTooLongException, generated.packet)


class PacketForm(unittest.TestCase):
    def test_transaction_id(self):
        """ID must be zero in a DNS-SD packet"""
        generated = r.DNSOutgoing(r._FLAGS_QR_QUERY)
        bytes = generated.packet()
        id = indexbytes(bytes, 0) << 8 | indexbytes(bytes, 1)
        self.assertEqual(id, 0)

    def test_query_header_bits(self):
        generated = r.DNSOutgoing(r._FLAGS_QR_QUERY)
        bytes = generated.packet()
        flags = indexbytes(bytes, 2) << 8 | indexbytes(bytes, 3)
        self.assertEqual(flags, 0x0)

    def test_response_header_bits(self):
        generated = r.DNSOutgoing(r._FLAGS_QR_RESPONSE)
        bytes = generated.packet()
        flags = indexbytes(bytes, 2) << 8 | indexbytes(bytes, 3)
        self.assertEqual(flags, 0x8000)

    def test_numbers(self):
        generated = r.DNSOutgoing(r._FLAGS_QR_RESPONSE)
        bytes = generated.packet()
        (numQuestions, numAnswers, numAuthorities, numAdditionals) = struct.unpack(
            "!4H", bytes[4:12]
        )
        self.assertEqual(numQuestions, 0)
        self.assertEqual(numAnswers, 0)
        self.assertEqual(numAuthorities, 0)
        self.assertEqual(numAdditionals, 0)

    def test_numbers_questions(self):
        generated = r.DNSOutgoing(r._FLAGS_QR_RESPONSE)
        question = r.DNSQuestion("testname.local.", r._TYPE_SRV, r._CLASS_IN)
        for i in xrange(10):
            generated.add_question(question)
        bytes = generated.packet()
        (numQuestions, numAnswers, numAuthorities, numAdditionals) = struct.unpack(
            "!4H", bytes[4:12]
        )
        self.assertEqual(numQuestions, 10)
        self.assertEqual(numAnswers, 0)
        self.assertEqual(numAuthorities, 0)
        self.assertEqual(numAdditionals, 0)


class Names(unittest.TestCase):
    def test_long_name(self):
        generated = r.DNSOutgoing(r._FLAGS_QR_RESPONSE)
        question = r.DNSQuestion(
            "this.is.a.very.long.name.with.lots.of.parts.in.it.local.",
            r._TYPE_SRV,
            r._CLASS_IN,
        )
        generated.add_question(question)
        r.DNSIncoming(generated.packet())

    def test_exceedingly_long_name(self):
        generated = r.DNSOutgoing(r._FLAGS_QR_RESPONSE)
        name = "%slocal." % ("part." * 1000)
        question = r.DNSQuestion(name, r._TYPE_SRV, r._CLASS_IN)
        generated.add_question(question)
        r.DNSIncoming(generated.packet())

    def test_exceedingly_long_name_part(self):
        name = "%s.local." % ("a" * 1000)
        generated = r.DNSOutgoing(r._FLAGS_QR_RESPONSE)
        question = r.DNSQuestion(name, r._TYPE_SRV, r._CLASS_IN)
        generated.add_question(question)
        self.assertRaises(r.NamePartTooLongException, generated.packet)

    def test_same_name(self):
        name = "paired.local."
        generated = r.DNSOutgoing(r._FLAGS_QR_RESPONSE)
        question = r.DNSQuestion(name, r._TYPE_SRV, r._CLASS_IN)
        generated.add_question(question)
        generated.add_question(question)
        r.DNSIncoming(generated.packet())

    def test_lots_of_names(self):

        # instantiate a zeroconf instance
        zc = Zeroconf(interfaces=["127.0.0.1"])

        # create a bunch of servers
        type_ = "_my-service._tcp.local."
        name = "a wonderful service"
        server_count = 300
        self.generate_many_hosts(zc, type_, name, server_count)

        # verify that name changing works
        self.verify_name_change(zc, type_, name, server_count)

        # we are going to monkey patch the zeroconf send to check packet sizes
        old_send = zc.send

        # needs to be a list so that we can modify it in our phony send
        longest_packet = [0, None]

        def send(out, addr=r._MDNS_ADDR, port=r._MDNS_PORT):
            """Sends an outgoing packet."""
            packet = out.packet()
            if longest_packet[0] < len(packet):
                longest_packet[0] = len(packet)
                longest_packet[1] = out
            old_send(out, addr=addr, port=port)

        # monkey patch the zeroconf send
        zc.send = send

        # dummy service callback
        def on_service_state_change(zeroconf, service_type, state_change, name):
            pass

        # start a browser
        browser = ServiceBrowser(zc, type_, [on_service_state_change])

        # wait until the browse request packet has maxed out in size
        sleep_count = 0
        while sleep_count < 100 and longest_packet[0] < r._MAX_MSG_ABSOLUTE - 100:
            sleep_count += 1
            time.sleep(0.1)

        browser.cancel()
        time.sleep(0.5)

        import zeroconf

        zeroconf.log.debug("sleep_count %d, sized %d", sleep_count, longest_packet[0])

        # now the browser has sent at least one request, verify the size
        assert longest_packet[0] <= r._MAX_MSG_ABSOLUTE
        assert longest_packet[0] >= r._MAX_MSG_ABSOLUTE - 100

        # mock zeroconf's logger warning() and debug()
        from mock import patch

        patch_warn = patch("zeroconf.log.warning")
        patch_debug = patch("zeroconf.log.debug")
        mocked_log_warn = patch_warn.start()
        mocked_log_debug = patch_debug.start()

        # now that we have a long packet in our possession, let's verify the
        # exception handling.
        out = longest_packet[1]
        out.data.append(b"\0" * 1000)

        # mock the zeroconf logger and check for the correct logging backoff
        call_counts = mocked_log_warn.call_count, mocked_log_debug.call_count
        # try to send an oversized packet
        zc.send(out)
        assert mocked_log_warn.call_count == call_counts[0] + 1
        assert mocked_log_debug.call_count == call_counts[0]
        zc.send(out)
        assert mocked_log_warn.call_count == call_counts[0] + 1
        assert mocked_log_debug.call_count == call_counts[0] + 1

        # force a receive of an oversized packet
        packet = out.packet()
        s = list(zc._respond_sockets.values())[0]

        # mock the zeroconf logger and check for the correct logging backoff
        call_counts = mocked_log_warn.call_count, mocked_log_debug.call_count
        # force receive on oversized packet
        s.sendto(packet, 0, (r._MDNS_ADDR, r._MDNS_PORT))
        s.sendto(packet, 0, (r._MDNS_ADDR, r._MDNS_PORT))
        time.sleep(2.0)
        zeroconf.log.debug(
            "warn %d debug %d was %s",
            mocked_log_warn.call_count,
            mocked_log_debug.call_count,
            call_counts,
        )
        assert mocked_log_debug.call_count > call_counts[0]

        # close our zeroconf which will close the sockets
        zc.close()

        # pop the big chunk off the end of the data and send on a closed socket
        out.data.pop()
        zc._GLOBAL_DONE = Event()

        # mock the zeroconf logger and check for the correct logging backoff
        call_counts = mocked_log_warn.call_count, mocked_log_debug.call_count
        # send on a closed socket (force a socket error)
        zc.send(out)
        zeroconf.log.debug(
            "warn %d debug %d was %s",
            mocked_log_warn.call_count,
            mocked_log_debug.call_count,
            call_counts,
        )
        assert mocked_log_warn.call_count > call_counts[0]
        assert mocked_log_debug.call_count > call_counts[0]
        zc.send(out)
        zeroconf.log.debug(
            "warn %d debug %d was %s",
            mocked_log_warn.call_count,
            mocked_log_debug.call_count,
            call_counts,
        )
        assert mocked_log_debug.call_count > call_counts[0] + 2

        mocked_log_warn.stop()
        mocked_log_debug.stop()

    def verify_name_change(self, zc, type_, name, number_hosts):
        desc = {"path": "/~paulsm/"}
        info_service = ServiceInfo(
            type_,
            "%s.%s" % (name, type_),
            socket.inet_aton("10.0.1.2"),
            80,
            0,
            0,
            desc,
            "ash-2.local.",
        )

        # verify name conflict
        self.assertRaises(r.NonUniqueNameException, zc.register_service, info_service)

        zc.register_service(info_service, allow_name_change=True)
        assert info_service.name.split(".")[0] == "%s-%d" % (name, number_hosts + 1)

    def generate_many_hosts(self, zc, type_, name, number_hosts):
        records_per_server = 2
        block_size = 25
        number_hosts = int(((number_hosts - 1) / block_size + 1)) * block_size
        for i in range(1, number_hosts + 1):
            next_name = name if i == 1 else "%s-%d" % (name, i)
            self.generate_host(zc, next_name, type_)
            if i % block_size == 0:
                sleep_count = 0
                while sleep_count < 40 and i * records_per_server > len(
                    zc.cache.entries_with_name(type_)
                ):
                    sleep_count += 1
                    time.sleep(0.05)

    @staticmethod
    def generate_host(zc, host_name, type_):
        name = ".".join((host_name, type_))
        out = r.DNSOutgoing(r._FLAGS_QR_RESPONSE | r._FLAGS_AA)
        out.add_answer_at_time(
            r.DNSPointer(type_, r._TYPE_PTR, r._CLASS_IN, r._DNS_TTL, name), 0
        )
        out.add_answer_at_time(
            r.DNSService(type_, r._TYPE_SRV, r._CLASS_IN, r._DNS_TTL, 0, 0, 80, name), 0
        )
        zc.send(out)


class Framework(unittest.TestCase):
    def test_launch_and_close(self):
        rv = r.Zeroconf(interfaces=r.InterfaceChoice.All)
        rv.close()
        rv = r.Zeroconf(interfaces=r.InterfaceChoice.Default)
        rv.close()


class Exceptions(unittest.TestCase):

    browser = None

    @classmethod
    def setUpClass(cls):
        cls.browser = Zeroconf(interfaces=["127.0.0.1"])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.browser = None

    def test_bad_service_info_name(self):
        self.assertRaises(
            r.BadTypeInNameException, self.browser.get_service_info, "type", "type_not"
        )

    def test_bad_service_names(self):
        bad_names_to_try = (
            "",
            "local",
            "_tcp.local.",
            "_udp.local.",
            "._udp.local.",
            "_@._tcp.local.",
            "_A@._tcp.local.",
            "_x--x._tcp.local.",
            "_-x._udp.local.",
            "_x-._tcp.local.",
            "_22._udp.local.",
            "_2-2._tcp.local.",
            "_1234567890-abcde._udp.local.",
            "\x00._x._udp.local.",
        )
        for name in bad_names_to_try:
            self.assertRaises(
                r.BadTypeInNameException,
                self.browser.get_service_info,
                name,
                "x." + name,
            )

    def test_good_instance_names(self):
        good_names_to_try = (
            ".._x._tcp.local.",
            "x.sub._http._tcp.local.",
            "6d86f882b90facee9170ad3439d72a4d6ee9f511._zget._http._tcp.local.",
        )
        for name in good_names_to_try:
            r.service_type_name(name)

    def test_bad_types(self):
        bad_names_to_try = (
            "._x._tcp.local.",
            "a" * 64 + "._sub._http._tcp.local.",
            "a" * 62 + u"â._sub._http._tcp.local.",
        )
        for name in bad_names_to_try:
            self.assertRaises(r.BadTypeInNameException, r.service_type_name, name)

    def test_bad_sub_types(self):
        bad_names_to_try = (
            "_sub._http._tcp.local.",
            "._sub._http._tcp.local.",
            "\x7f._sub._http._tcp.local.",
            "\x1f._sub._http._tcp.local.",
        )
        for name in bad_names_to_try:
            self.assertRaises(r.BadTypeInNameException, r.service_type_name, name)

    def test_good_service_names(self):
        good_names_to_try = (
            "_x._tcp.local.",
            "_x._udp.local.",
            "_12345-67890-abc._udp.local.",
            "x._sub._http._tcp.local.",
            "a" * 63 + "._sub._http._tcp.local.",
            "a" * 61 + u"â._sub._http._tcp.local.",
        )
        for name in good_names_to_try:
            r.service_type_name(name)


class TestDnsIncoming(unittest.TestCase):
    def test_incoming_exception_handling(self):
        generated = r.DNSOutgoing(0)
        packet = generated.packet()
        packet = packet[:8] + b"deadbeef" + packet[8:]
        parsed = r.DNSIncoming(packet)
        parsed = r.DNSIncoming(packet)
        assert parsed.valid is False

    def test_incoming_unknown_type(self):
        generated = r.DNSOutgoing(0)
        answer = r.DNSAddress("a", r._TYPE_SOA, r._CLASS_IN, 1, b"a")
        generated.add_additional_answer(answer)
        packet = generated.packet()
        parsed = r.DNSIncoming(packet)
        assert len(parsed.answers) == 0
        assert parsed.is_query() != parsed.is_response()

    def test_incoming_ipv6(self):
        # ::TODO:: could use a test here if we add IPV6 record handling
        # ie: _TYPE_AAAA
        pass


class TestRegistrar(unittest.TestCase):
    def test_ttl(self):

        # instantiate a zeroconf instance
        zc = Zeroconf(interfaces=["127.0.0.1"])

        # service definition
        type_ = "_test-srvc-type._tcp.local."
        name = "xxxyyy"
        registration_name = "%s.%s" % (name, type_)

        desc = {"path": "/~paulsm/"}
        info = ServiceInfo(
            type_,
            registration_name,
            socket.inet_aton("10.0.1.2"),
            80,
            0,
            0,
            desc,
            "ash-2.local.",
        )

        # we are going to monkey patch the zeroconf send to check packet sizes
        old_send = zc.send

        # needs to be a list so that we can modify it in our phony send
        nbr_answers = [0, None]
        nbr_additionals = [0, None]
        nbr_authorities = [0, None]

        def send(out, addr=r._MDNS_ADDR, port=r._MDNS_PORT, interface=None):
            """Sends an outgoing packet."""
            for answer, time_ in out.answers:
                nbr_answers[0] += 1
                assert answer.ttl == expected_ttl
            for answer in out.additionals:
                nbr_additionals[0] += 1
                assert answer.ttl == expected_ttl
            for answer in out.authorities:
                nbr_authorities[0] += 1
                assert answer.ttl == expected_ttl
            old_send(out, addr=addr, port=port, interface=interface)

        # monkey patch the zeroconf send
        zc.send = send

        # register service with default TTL
        expected_ttl = r._DNS_TTL
        zc.register_service(info)
        assert (
            nbr_answers[0] == 12 and nbr_additionals[0] == 0 and nbr_authorities[0] == 3
        )
        nbr_answers[0] = nbr_additionals[0] = nbr_authorities[0] = 0

        # query
        query = r.DNSOutgoing(r._FLAGS_QR_QUERY | r._FLAGS_AA)
        query.add_question(r.DNSQuestion(info.type, r._TYPE_PTR, r._CLASS_IN))
        query.add_question(r.DNSQuestion(info.name, r._TYPE_SRV, r._CLASS_IN))
        query.add_question(r.DNSQuestion(info.name, r._TYPE_TXT, r._CLASS_IN))
        query.add_question(r.DNSQuestion(info.server, r._TYPE_A, r._CLASS_IN))
        zc.handle_query(query, r._MDNS_ADDR, r._MDNS_PORT)
        assert (
            nbr_answers[0] == 4 and nbr_additionals[0] == 1 and nbr_authorities[0] == 0
        )
        nbr_answers[0] = nbr_additionals[0] = nbr_authorities[0] = 0

        # unregister
        expected_ttl = 0
        zc.unregister_service(info)
        assert (
            nbr_answers[0] == 12 and nbr_additionals[0] == 0 and nbr_authorities[0] == 0
        )
        nbr_answers[0] = nbr_additionals[0] = nbr_authorities[0] = 0

        # register service with custom TTL
        expected_ttl = r._DNS_TTL * 2
        assert expected_ttl != r._DNS_TTL
        zc.register_service(info, ttl=expected_ttl)
        assert (
            nbr_answers[0] == 12 and nbr_additionals[0] == 0 and nbr_authorities[0] == 3
        )
        nbr_answers[0] = nbr_additionals[0] = nbr_authorities[0] = 0

        # query
        query = r.DNSOutgoing(r._FLAGS_QR_QUERY | r._FLAGS_AA)
        query.add_question(r.DNSQuestion(info.type, r._TYPE_PTR, r._CLASS_IN))
        query.add_question(r.DNSQuestion(info.name, r._TYPE_SRV, r._CLASS_IN))
        query.add_question(r.DNSQuestion(info.name, r._TYPE_TXT, r._CLASS_IN))
        query.add_question(r.DNSQuestion(info.server, r._TYPE_A, r._CLASS_IN))
        zc.handle_query(query, r._MDNS_ADDR, r._MDNS_PORT)
        assert (
            nbr_answers[0] == 4 and nbr_additionals[0] == 1 and nbr_authorities[0] == 0
        )
        nbr_answers[0] = nbr_additionals[0] = nbr_authorities[0] = 0

        # unregister
        expected_ttl = 0
        zc.unregister_service(info)
        assert (
            nbr_answers[0] == 12 and nbr_additionals[0] == 0 and nbr_authorities[0] == 0
        )
        nbr_answers[0] = nbr_additionals[0] = nbr_authorities[0] = 0


class TestDNSCache(unittest.TestCase):
    def test_order(self):
        record1 = r.DNSAddress("a", r._TYPE_SOA, r._CLASS_IN, 1, b"a")
        record2 = r.DNSAddress("a", r._TYPE_SOA, r._CLASS_IN, 1, b"b")
        cache = r.DNSCache()
        cache.add(record1)
        cache.add(record2)
        entry = r.DNSEntry("a", r._TYPE_SOA, r._CLASS_IN)
        cached_record = cache.get(entry)
        self.assertEqual(cached_record, record2)


class ServiceTypesQuery(unittest.TestCase):
    def test_integration_with_listener(self):

        type_ = "_test-srvc-type._tcp.local."
        name = "xxxyyy"
        registration_name = "%s.%s" % (name, type_)

        zeroconf_registrar = Zeroconf(interfaces=["127.0.0.1"])
        desc = {"path": "/~paulsm/"}
        info = ServiceInfo(
            type_,
            registration_name,
            socket.inet_aton("10.0.1.2"),
            80,
            0,
            0,
            desc,
            "ash-2.local.",
        )
        zeroconf_registrar.register_service(info)

        try:
            service_types = ZeroconfServiceTypes.find(
                interfaces=["127.0.0.1"], timeout=0.5
            )
            assert type_ in service_types
            service_types = ZeroconfServiceTypes.find(
                zc=zeroconf_registrar, timeout=0.5
            )
            assert type_ in service_types

        finally:
            zeroconf_registrar.close()

    def test_integration_with_subtype_and_listener(self):
        subtype_ = "_subtype._sub"
        type_ = "_type._tcp.local."
        name = "xxxyyy"
        # Note: discovery returns only DNS-SD type not subtype
        discovery_type = "%s.%s" % (subtype_, type_)
        registration_name = "%s.%s" % (name, type_)

        zeroconf_registrar = Zeroconf(interfaces=["127.0.0.1"])
        desc = {"path": "/~paulsm/"}
        info = ServiceInfo(
            discovery_type,
            registration_name,
            socket.inet_aton("10.0.1.2"),
            80,
            0,
            0,
            desc,
            "ash-2.local.",
        )
        zeroconf_registrar.register_service(info)

        try:
            service_types = ZeroconfServiceTypes.find(
                interfaces=["127.0.0.1"], timeout=0.5
            )
            assert discovery_type in service_types
            service_types = ZeroconfServiceTypes.find(
                zc=zeroconf_registrar, timeout=0.5
            )
            assert discovery_type in service_types

        finally:
            zeroconf_registrar.close()


class ListenerTest(unittest.TestCase):
    def test_integration_with_listener_class(self):

        service_added = Event()
        service_removed = Event()
        service_updated = Event()

        subtype_name = u"My special Subtype"
        type_ = u"_http._tcp.local."
        subtype = subtype_name + u"._sub." + type_
        name = u"xxxyyy"
        registration_name = u"%s.%s" % (name, subtype)

        class MyListener(object):
            def add_service(self, zeroconf, type, name):
                zeroconf.get_service_info(type, name)
                service_added.set()

            def remove_service(self, zeroconf, type, name):
                service_removed.set()

        class MySubListener(r.ServiceListener):
            def add_service(self, zeroconf, type, name):
                pass

            def remove_service(self, zeroconf, type, name):
                pass

            def update_service(self, zeroconf, type, name):
                service_updated.set()

        listener = MyListener()
        zeroconf_browser = Zeroconf(interfaces=["127.0.0.1"])
        zeroconf_browser.add_service_listener(subtype, listener)

        properties = dict(
            prop_none=None,
            prop_string=b"a_prop",
            prop_float=1.0,
            prop_blank=b"a blanked string",
            prop_true=1,
            prop_false=0,
        )

        zeroconf_registrar = Zeroconf(interfaces=["127.0.0.1"])
        desc = {"path": "/~paulsm/"}
        desc.update(properties)
        info_service = ServiceInfo(
            subtype,
            registration_name,
            socket.inet_aton("10.0.1.2"),
            80,
            0,
            0,
            desc,
            "ash-2.local.",
        )
        zeroconf_registrar.register_service(info_service)

        try:
            service_added.wait(1)
            assert service_added.is_set()

            # short pause to allow multicast timers to expire
            time.sleep(3)

            # clear the answer cache to force query
            for record in zeroconf_browser.cache.entries():
                zeroconf_browser.cache.remove(record)

            # get service info without answer cache
            info = zeroconf_browser.get_service_info(type_, registration_name)

            assert info.properties[b"prop_none"] is False
            assert info.properties[b"prop_string"] == properties["prop_string"]
            assert info.properties[b"prop_float"] is False
            assert info.properties[b"prop_blank"] == properties["prop_blank"]
            assert info.properties[b"prop_true"] is True
            assert info.properties[b"prop_false"] is False

            info = zeroconf_browser.get_service_info(subtype, registration_name)
            assert info.properties[b"prop_none"] is False

            # Begin material test addition
            sublistener = MySubListener()
            zeroconf_browser.add_service_listener(registration_name, sublistener)
            properties["prop_blank"] = b"an updated string"
            desc.update(properties)
            info_service = ServiceInfo(
                subtype,
                registration_name,
                socket.inet_aton("10.0.1.2"),
                80,
                0,
                0,
                desc,
                "ash-2.local.",
            )
            zeroconf_registrar.update_service(info_service)
            service_updated.wait(2)
            assert service_updated.is_set()

            info = zeroconf_browser.get_service_info(type_, registration_name)
            assert info is not None
            assert info.properties[b"prop_blank"] == properties["prop_blank"]
            # End material test addition

            zeroconf_registrar.unregister_service(info_service)
            service_removed.wait(2)
            assert service_removed.is_set()

        finally:
            zeroconf_registrar.close()
            zeroconf_browser.remove_service_listener(listener)
            zeroconf_browser.close()


def _init_zeroconf_browser(service_type, registration_name):
    service_added = Event()
    service_removed = Event()

    def on_service_state_change(zeroconf, service_type, state_change, name):
        if name == registration_name:
            if state_change is ServiceStateChange.Added:
                service_added.set()
            elif state_change is ServiceStateChange.Removed:
                service_removed.set()

    zeroconf_browser = Zeroconf(interfaces=["127.0.0.1"])
    browser = ServiceBrowser(zeroconf_browser, service_type, [on_service_state_change])
    zeroconf_browser.browsers["test"] = browser
    return zeroconf_browser, service_added, service_removed


def test_add_remove_interfaces_integration():
    type_ = "_http._tcp.local."
    registration_name = "xxxyyy.%s" % type_

    zeroconf_browser, service_added, service_removed = _init_zeroconf_browser(type_, registration_name)

    expected_ttl = r._DNS_TTL
    time_offset = 0

    def current_time_millis():
        """Current system time in milliseconds"""
        return time.time() * 1000 + time_offset * 1000

    # monkey patch the zeroconf current_time_millis
    r.current_time_millis = current_time_millis

    zeroconf_registrar = Zeroconf(interfaces=[])
    desc = {"path": "/~paulsm/"}
    info = ServiceInfo(
        type_,
        registration_name,
        socket.inet_aton("10.0.1.2"),
        80,
        0,
        0,
        desc,
        "ash-2.local.",
    )
    zeroconf_registrar.register_service(info)

    try:
        # no interfaces have been added yet, so nothing to register that our service has been added yet
        service_added.wait(1)
        assert not service_added.is_set()

        zeroconf_registrar.update_interfaces(interfaces=["127.0.0.1"])
        zeroconf_browser.notify_all()

        # make sure we got the service added event, which could take as long as the TTL to happen
        service_added.wait(expected_ttl)
        assert service_added.is_set()

        # now remove the interface to trigger removal event
        assert not service_removed.is_set()
        zeroconf_registrar.update_interfaces(interfaces=[])
        zeroconf_browser.notify_all()

        service_removed.wait(expected_ttl)
        assert service_removed.is_set()
    finally:
        zeroconf_registrar.close()
        zeroconf_browser.close()


def test_integration():
    unexpected_ttl = Event()
    got_query = Event()

    type_ = "_http._tcp.local."
    registration_name = "xxxyyy.%s" % type_

    zeroconf_browser, service_added, service_removed = _init_zeroconf_browser(type_, registration_name)

    # we are going to monkey patch the zeroconf send to check packet sizes
    old_send = zeroconf_browser.send

    time_offset = 0

    def current_time_millis():
        """Current system time in milliseconds"""
        return time.time() * 1000 + time_offset * 1000

    expected_ttl = r._DNS_TTL

    # needs to be a list so that we can modify it in our phony send
    nbr_queries = [0, None]

    def send(out, addr=r._MDNS_ADDR, port=r._MDNS_PORT, interface=None):
        """Sends an outgoing packet."""
        pout = r.DNSIncoming(out.packet())

        for answer in pout.answers:
            nbr_queries[0] += 1
            if not answer.ttl > expected_ttl / 2:
                unexpected_ttl.set()

        got_query.set()
        old_send(out, addr=addr, port=port, interface=interface)

    # monkey patch the zeroconf send
    zeroconf_browser.send = send

    # monkey patch the zeroconf current_time_millis
    r.current_time_millis = current_time_millis

    zeroconf_registrar = Zeroconf(interfaces=["127.0.0.1"])
    desc = {"path": "/~paulsm/"}
    info = ServiceInfo(
        type_,
        registration_name,
        socket.inet_aton("10.0.1.2"),
        80,
        0,
        0,
        desc,
        "ash-2.local.",
    )
    zeroconf_registrar.register_service(info)

    try:
        service_added.wait(1)
        assert service_added.is_set()

        sleep_count = 0
        while nbr_queries[0] < 50:
            time_offset += expected_ttl / 4
            zeroconf_browser.notify_all()
            sleep_count += 1
            got_query.wait(1)
            got_query.clear()
        assert not unexpected_ttl.is_set()

        # Don't remove service, allow close() to cleanup

    finally:
        zeroconf_registrar.close()
        service_removed.wait(1)
        assert service_removed.is_set()
        zeroconf_browser.close()
