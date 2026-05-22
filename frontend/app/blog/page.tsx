export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

import { Nav } from '@/components/Nav';
import { getStats, getMonthlyCounts } from '@/lib/db';

const API_BASE = process.env.NEXT_PUBLIC_VPS_API || '';

async function fetchLandscape() {
  if (!API_BASE) return null;
  try {
    const res = await fetch(`${API_BASE}/api/landscape`, { next: { revalidate: 300 } });
    if (res.ok) return res.json();
  } catch {}
  return null;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-12">
      <h2 className="text-xl font-bold mb-4 pb-2 border-b-2 border-[#EF7C00]" style={{ color: 'var(--text-1)' }}>
        {title}
      </h2>
      {children}
    </section>
  );
}

function StatCard({ val, lbl }: { val: string; lbl: string }) {
  return (
    <div className="rounded-lg p-4 text-center border-t-[3px]" style={{ background: 'var(--surface-alt)', borderColor: 'var(--blue)' }}>
      <div className="text-2xl font-black" style={{ color: 'var(--blue)' }}>{val}</div>
      <div className="text-[0.7rem] uppercase tracking-wide mt-1" style={{ color: 'var(--text-3)' }}>{lbl}</div>
    </div>
  );
}

/* ── Blog Post ─────────────────────────────────────── */

export default async function BlogPage() {
  const landscape = await fetchLandscape();

  return (
    <>
      <Nav activePage="blog" />

      {/* Header */}
      <header className="text-white px-6 py-12" style={{ background: 'linear-gradient(135deg, #003D7C 0%, #00509E 100%)' }}>
        <div className="max-w-3xl mx-auto text-center">
          <p className="text-[0.8rem] uppercase tracking-widest text-white/60 mb-2">Data Analysis</p>
          <h1 className="text-2xl font-bold leading-tight">
            Inside NUSConfessIT: What 72,000 Confessions Reveal About NUS Students
          </h1>
          <p className="text-white/70 mt-3 text-sm max-w-xl mx-auto">
            A deep dive into the embedding landscape, viral dynamics, and thematic structure of Singapore's largest anonymous confession platform.
          </p>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 pb-20 pt-10">

        {/* ── Introduction ── */}
        <Section title="Introduction">
          <p className="text-[0.92rem] leading-relaxed mb-3" style={{ color: 'var(--text-2)' }}>
            NUSConfessIT is a Telegram-based anonymous confession channel serving the NUS community. Since February 2024, 
            it's accumulated over <strong>72,000 confessions</strong>, generating <strong>129 million views</strong> 
            and countless reactions, replies, and discussions.
          </p>
          <p className="text-[0.92rem] leading-relaxed mb-3" style={{ color: 'var(--text-2)' }}>
            But what are students actually confessing about? Which topics go viral? And can we predict what 
            content will blow up? This analysis uses ML embeddings, dimensionality reduction, and clustering 
            to map the confession landscape.
          </p>
        </Section>

        {/* ── Key Numbers ── */}
        <Section title="At a Glance">
          <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))' }}>
            <StatCard val="72,172" lbl="Total Confessions" />
            <StatCard val="129M" lbl="Total Views" />
            <StatCard val="816" lbl="Days Active" />
            <StatCard val="23.3" lbl="Mean Score" />
            <StatCard val="11,121" lbl="Highest Score" />
            <StatCard val="26%" lbl="Viral Rate" />
          </div>
        </Section>

        {/* ── Score Distribution ── */}
        <Section title="The Score Distribution — A Long Tail of Engagement">
          <div className="mb-4">
            <img src="/blog/score_distribution.png" alt="Score distribution histogram" className="w-full rounded-lg shadow-sm" style={{ background: 'var(--surface)' }} />
          </div>
          <p className="text-[0.92rem] leading-relaxed mb-3" style={{ color: 'var(--text-2)' }}>
            Engagement follows a <strong>heavily skewed distribution</strong>. The median post scores just <strong>15</strong>, 
            while the most viral post hit <strong>11,121</strong> — a 740× gap. The top 25% threshold sits at <strong>28</strong>,
            meaning 75% of all confessions cluster in a narrow low-engagement band.
          </p>
          <p className="text-[0.92rem] leading-relaxed" style={{ color: 'var(--text-2)' }}>
            This is classic social media dynamics: a small fraction of content captures most attention. The challenge 
            is identifying <em>which</em> posts break through.
          </p>
        </Section>

        {/* ── Category Breakdown ── */}
        <Section title="What Students Confess About">
          <div className="mb-4">
            <img src="/blog/category_breakdown.png" alt="Category breakdown bar chart" className="w-full rounded-lg shadow-sm" style={{ background: 'var(--surface)' }} />
          </div>
          <p className="text-[0.92rem] leading-relaxed mb-3" style={{ color: 'var(--text-2)' }}>
            The raw category data has a problem: <strong>78% of posts are uncategorised</strong> — they were posted 
            before the tag system was introduced, or the confessor chose not to use it. Among tagged posts, the 
            dominant categories are <strong>others</strong> (21.7%), with tiny fragments making up the rest.
          </p>
          <p className="text-[0.92rem] leading-relaxed" style={{ color: 'var(--text-2)' }}>
            This is why we need embedding-based clustering — the categories alone don't tell us enough. By looking 
            at the <em>semantic content</em> of every post, we can build a more meaningful taxonomy.
          </p>
        </Section>

        {/* ── Monthly Activity ── */}
        <Section title="Growth Over Time — A Channel in Its Prime">
          <div className="mb-4">
            <img src="/blog/monthly_activity.png" alt="Monthly activity bar chart" className="w-full rounded-lg shadow-sm" style={{ background: 'var(--surface)' }} />
          </div>
          <p className="text-[0.92rem] leading-relaxed mb-3" style={{ color: 'var(--text-2)' }}>
            Since launching in February 2024, the channel has grown from a few hundred posts per month to 
            <strong> sustained volumes of 3,000+ posts monthly</strong>. The peak occurred in late 2024, 
            coinciding with the start of the academic year and major campus events.
          </p>
          <p className="text-[0.92rem] leading-relaxed" style={{ color: 'var(--text-2)' }}>
            The channel's longevity (816 days and counting) is unusual for anonymous confession pages, which 
            typically burn out within months. NUSConfessIT's continued relevance suggests it fills a genuine 
            community need.
          </p>
        </Section>

        {/* ── Embedding Landscape ── */}
        <Section title="Mapping the Confession Universe">
          <div className="mb-4">
            <img src="/blog/umap_landscape.png" alt="UMAP embedding landscape" className="w-full rounded-lg shadow-sm" style={{ background: 'var(--surface)' }} />
          </div>
          <p className="text-[0.92rem] leading-relaxed mb-3" style={{ color: 'var(--text-2)' }}>
            We embedded all 72K confessions using <strong>OpenAI text-embedding-3-small</strong> (512 dimensions), 
            then projected them into 2D using <strong>UMAP</strong>. The resulting landscape reveals a 
            <strong>continuous gradient</strong> rather than hard cluster boundaries — confessions blend into 
            one another along thematic axes.
          </p>
          <p className="text-[0.92rem] leading-relaxed mb-3" style={{ color: 'var(--text-2)' }}>
            The left plot shows every post as a dot, with <strong style={{ color: '#EF7C00' }}>viral posts (top 25%)</strong> 
            highlighted in orange. The right plot reveals <strong>score intensity</strong> — hotter colours 
            indicate higher engagement. Notice how viral posts concentrate in specific regions rather than 
            being uniformly distributed.
          </p>

          <h3 className="text-base font-bold mt-6 mb-3" style={{ color: 'var(--text-1)' }}>
            Four Main Regions
          </h3>
          {landscape?.cluster_taxonomy?.["4_main_regions"] && (
            <div className="space-y-3 mb-4">
              {Object.entries(landscape.cluster_taxonomy["4_main_regions"]).map(([key, val]: [string, any]) => {
                const label = key.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase());
                return (
                  <div key={key} className="rounded-lg p-4" style={{ background: 'var(--surface-alt)' }}>
                    <div className="flex justify-between items-center mb-1">
                      <span className="font-bold" style={{ color: 'var(--text-1)' }}>{label}</span>
                      <span className="font-bold" style={{ color: 'var(--blue)' }}>{val.size_pct}%</span>
                    </div>
                    <div className="h-[8px] rounded-full overflow-hidden" style={{ background: 'var(--surface-mid)' }}>
                      <div className="h-full rounded-full" style={{ width: `${val.size_pct}%`, background: 'linear-gradient(90deg, var(--blue), var(--blue-mid))' }} />
                    </div>
                    <div className="text-[0.78rem] mt-1" style={{ color: 'var(--text-muted)' }}>
                      Keywords: {val.keywords}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          <p className="text-[0.88rem] leading-relaxed" style={{ color: 'var(--text-2)' }}>
            The landscape splits into four broad regions: <strong>Academics</strong> (32%) covering mods, finals, 
            and coursework; <strong>Career & Hot Takes</strong> (31%) with internships, LinkedIn drama, and hustle 
            culture; <strong>Dating & Relationships</strong> (29%) dominating the romantic side of campus life; and 
            <strong>Lonely & Admin</strong> (8%) capturing the more isolated posts.
          </p>
        </Section>

        {/* ── Viral Insights ── */}
        <Section title="What Goes Viral">
          <div className="mb-4">
            <img src="/blog/viral_by_category.png" alt="Viral rate by category" className="w-full rounded-lg shadow-sm" style={{ background: 'var(--surface)' }} />
          </div>
          <p className="text-[0.92rem] leading-relaxed mb-3" style={{ color: 'var(--text-2)' }}>
            The single most important finding: <strong>dating & relationship content dramatically outperforms everything else</strong>.
            The viral rate among dating-region posts is <strong style={{ color: '#EF7C00' }}>~32%</strong>, compared to 
            ~23-25% for academics and career posts. This isn't a small edge — it's a <strong>~40% relative increase</strong> 
            in viral probability.
          </p>
          <p className="text-[0.92rem] leading-relaxed mb-3" style={{ color: 'var(--text-2)' }}>
            This makes intuitive sense: anonymous platforms lower the barrier for sharing personal romantic stories 
            that people are reluctant to discuss publicly. The most viral post ever (score 11,121) was a whistleblowing 
            post about a hall resident contracting an STD — a story that combines romance, scandal, and campus gossip.
          </p>
          <div className="rounded-lg p-4 text-[0.9rem] leading-relaxed border-l-4 border-[#EF7C00]" style={{ background: 'var(--surface-alt)' }}>
            <strong style={{ color: '#EF7C00' }}>Key insight:</strong> If you want to go viral on NUSConfessIT, 
            <strong> talk about relationships</strong>. Romance plus scandal is the most powerful combination. 
            Pure academic complaints and career rants rarely break through the noise.
          </div>
        </Section>

        {/* ── Methodology ── */}
        <Section title="Methodology">
          <p className="text-[0.92rem] leading-relaxed mb-2" style={{ color: 'var(--text-2)' }}>
            <strong>Embedding:</strong> Each confession was encoded using <code>text-embedding-3-small</code> 
            (512 dimensions), providing a dense semantic representation.
          </p>
          <p className="text-[0.92rem] leading-relaxed mb-2" style={{ color: 'var(--text-2)' }}>
            <strong>Dimensionality Reduction:</strong> UMAP with 15 nearest neighbours, minimum distance 0.1, 
            fit on a 15K sample then transformed across all 72K posts.
          </p>
          <p className="text-[0.92rem] leading-relaxed mb-2" style={{ color: 'var(--text-2)' }}>
            <strong>Clustering:</strong> Mean Shift (bandwidth=2.14) for region detection, validated against 
            HDBSCAN. Four stable regions identified with consistent keyword profiles.
          </p>
          <p className="text-[0.92rem] leading-relaxed mb-2" style={{ color: 'var(--text-2)' }}>
            <strong>Virality:</strong> Composite score = reactions + 2× replies + 3× forwards. Top 25% of 
            posts by score classified as viral.
          </p>
          <p className="text-[0.88rem] leading-relaxed mt-4" style={{ color: 'var(--text-muted)' }}>
            Analysis date: May 2026. Data collected via the Telegram API from t.me/NUSConfessIT.
          </p>
        </Section>

      </main>
    </>
  );
}