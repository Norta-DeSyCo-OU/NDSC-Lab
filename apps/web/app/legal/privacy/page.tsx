export const metadata = { title: "Privacy Policy" };

export default function PrivacyPage() {
  return (
    <article className="max-w-3xl mx-auto prose prose-invert">
      <h1>Privacy Policy</h1>
      <p>
        <strong>Norta DeSyCo OU</strong> (&quot;we&quot;, the &quot;Provider&quot;) operates NDSC
        Lab. This Privacy Policy explains what personal data we process and your rights under the
        EU General Data Protection Regulation (GDPR).
      </p>
      <h2>1. Data we collect</h2>
      <ul>
        <li>Account: email address, optional display name and profile fields.</li>
        <li>Content: items, comments, and other material you publish.</li>
        <li>Authentication: hashed passwords, session identifiers, IP address of recent logins.</li>
        <li>Analytics (only with your consent): per-user view events on content items.</li>
        <li>Audit log: actions you perform that are relevant to security or moderation.</li>
      </ul>
      <h2>2. Lawful basis</h2>
      <p>
        We process account and content data on the basis of contract (your agreement with us).
        Analytics are processed on the basis of consent. Audit logs are processed on the basis of
        legitimate interest in operating a secure service.
      </p>
      <h2>3. Per-user view tracking</h2>
      <p>
        If you accept the &quot;Analytics&quot; option in the cookie banner, we record an event each
        time you view a content item, associated with your account. We use this only to compute
        aggregate viewership for administrators. Raw events are retained for 90 days; aggregated
        counts are kept indefinitely.
      </p>
      <h2>4. Your rights</h2>
      <ul>
        <li>Access — request a copy of your data via your account settings (data export).</li>
        <li>Erasure — delete your account and data from your account settings.</li>
        <li>Portability — the data export ZIP includes all data you can take with you.</li>
        <li>Rectification — edit profile and content.</li>
        <li>Object / restrict — change your analytics consent at any time.</li>
      </ul>
      <h2>5. Data residency</h2>
      <p>
        All personal data is processed and stored within the European Union: compute resides in
        Hetzner (Germany); object storage on Cloudflare R2 EU jurisdiction.
      </p>
      <h2>6. Recipients</h2>
      <p>
        We use the following processors: Hetzner (hosting), Cloudflare (CDN/WAF), Resend
        (transactional email). They process data on our behalf under DPA agreements.
      </p>
      <h2>7. Retention</h2>
      <ul>
        <li>Account: until you delete it; max grace 30 days after request.</li>
        <li>Audit log: default 365 days, configurable.</li>
        <li>Analytics raw events: 90 days. Aggregates: indefinite.</li>
        <li>Login attempts: 90 days.</li>
      </ul>
      <h2>8. Contact</h2>
      <p>
        Data controller: Norta DeSyCo OU, Estonia. For privacy requests, email{" "}
        <code>privacy@</code> (domain TBD).
      </p>
      <p>
        <small>Version 2026-05-13.</small>
      </p>
    </article>
  );
}
