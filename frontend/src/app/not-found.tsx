import Link from "next/link";

export default function NotFound() {
  return (
    <section className="panel">
      <h1 className="text-3xl font-semibold">
        This corner of the farm is empty.
      </h1>
      <Link href="/" className="mt-6 inline-block text-green underline">
        Back to the dashboard
      </Link>
    </section>
  );
}
