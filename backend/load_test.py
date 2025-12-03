#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Load Testing Script for Medical Clinic Management System

Tests API endpoints under load to ensure production readiness.

Usage:
    python load_test.py [--users N] [--requests N] [--endpoint URL]
"""
import argparse
import asyncio
import time
from collections import defaultdict
from datetime import datetime
from typing import Dict, List

import aiohttp


class LoadTester:
    """Load testing tool"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.results = {
            "total_requests": 0,
            "successful": 0,
            "failed": 0,
            "errors": defaultdict(int),
            "response_times": [],
            "status_codes": defaultdict(int),
        }

    async def make_request(
        self, session: aiohttp.ClientSession, endpoint: str, method: str = "GET", **kwargs
    ):
        """Make a single HTTP request"""
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()

        try:
            async with session.request(method, url, **kwargs) as response:
                response_time = time.time() - start_time
                status = response.status

                self.results["total_requests"] += 1
                self.results["status_codes"][status] += 1
                self.results["response_times"].append(response_time)

                if 200 <= status < 300:
                    self.results["successful"] += 1
                else:
                    self.results["failed"] += 1
                    self.results["errors"][f"HTTP {status}"] += 1

                return {
                    "status": status,
                    "response_time": response_time,
                    "success": 200 <= status < 300,
                }

        except Exception as e:
            response_time = time.time() - start_time
            self.results["total_requests"] += 1
            self.results["failed"] += 1
            self.results["errors"][str(type(e).__name__)] += 1
            self.results["response_times"].append(response_time)

            return {
                "status": 0,
                "response_time": response_time,
                "success": False,
                "error": str(e),
            }

    async def test_endpoint(
        self, endpoint: str, num_requests: int = 100, concurrency: int = 10, **kwargs
    ):
        """Test a single endpoint with concurrent requests"""
        print(f"\n{'='*80}")
        print(f"Testing: {endpoint}")
        print(f"Requests: {num_requests}, Concurrency: {concurrency}")
        print(f"{'='*80}\n")

        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(concurrency)

        async def bounded_request(session, endpoint, **kwargs):
            async with semaphore:
                return await self.make_request(session, endpoint, **kwargs)

        async with aiohttp.ClientSession() as session:
            tasks = [
                bounded_request(session, endpoint, **kwargs)
                for _ in range(num_requests)
            ]

            start_time = time.time()
            results = await asyncio.gather(*tasks)
            total_time = time.time() - start_time

            return results, total_time

    def print_results(self, total_time: float):
        """Print test results"""
        results = self.results

        print(f"\n{'='*80}")
        print("LOAD TEST RESULTS")
        print(f"{'='*80}\n")

        print(f"Total Requests: {results['total_requests']}")
        print(f"Successful: {results['successful']} ({results['successful']/results['total_requests']*100:.1f}%)")
        print(f"Failed: {results['failed']} ({results['failed']/results['total_requests']*100:.1f}%)")
        print(f"Total Time: {total_time:.2f}s")
        print(f"Requests/sec: {results['total_requests']/total_time:.2f}")

        if results["response_times"]:
            times = results["response_times"]
            print(f"\nResponse Times:")
            print(f"  Min: {min(times)*1000:.2f}ms")
            print(f"  Max: {max(times)*1000:.2f}ms")
            print(f"  Avg: {sum(times)/len(times)*1000:.2f}ms")
            print(f"  Median: {sorted(times)[len(times)//2]*1000:.2f}ms")

        print(f"\nStatus Codes:")
        for status, count in sorted(results["status_codes"].items()):
            print(f"  {status}: {count}")

        if results["errors"]:
            print(f"\nErrors:")
            for error, count in results["errors"].items():
                print(f"  {error}: {count}")

        print(f"\n{'='*80}\n")

    async def run_test_suite(
        self, num_users: int = 10, requests_per_user: int = 10
    ):
        """Run a comprehensive test suite"""
        print(f"\n{'='*80}")
        print("LOAD TEST SUITE")
        print(f"{'='*80}")
        print(f"Started at: {datetime.now().isoformat()}")
        print(f"Concurrent Users: {num_users}")
        print(f"Requests per User: {requests_per_user}")
        print(f"Total Requests: {num_users * requests_per_user}")

        # Test endpoints
        endpoints = [
            ("/api/v1/health", "GET"),
            ("/api/v1/patients/", "GET"),
            ("/api/v1/services/", "GET"),
            ("/api/v1/departments/", "GET"),
        ]

        total_start = time.time()

        for endpoint, method in endpoints:
            await self.test_endpoint(
                endpoint,
                num_requests=requests_per_user * num_users,
                concurrency=num_users,
                method=method,
            )

        total_time = time.time() - total_start
        self.print_results(total_time)


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Load testing tool")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--users",
        type=int,
        default=10,
        help="Number of concurrent users (default: 10)",
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=10,
        help="Requests per user (default: 10)",
    )
    parser.add_argument(
        "--endpoint",
        help="Test a specific endpoint (optional)",
    )
    parser.add_argument(
        "--method",
        default="GET",
        help="HTTP method (default: GET)",
    )

    args = parser.parse_args()

    tester = LoadTester(base_url=args.url)

    if args.endpoint:
        # Test single endpoint
        results, total_time = await tester.test_endpoint(
            args.endpoint,
            num_requests=args.requests * args.users,
            concurrency=args.users,
            method=args.method,
        )
        tester.print_results(total_time)
    else:
        # Run full test suite
        await tester.run_test_suite(
            num_users=args.users, requests_per_user=args.requests
        )


if __name__ == "__main__":
    asyncio.run(main())


