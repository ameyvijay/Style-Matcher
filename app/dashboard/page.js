"use client";

import { useState, useEffect } from "react";
import AuthGuard from "../../components/AuthGuard";
import { motion } from "framer-motion";
import { BarChart3, TrendingUp, Target, ShieldAlert, ArrowLeft } from "lucide-react";
import Link from "next/link";
import styles from "./dashboard.module.css";

export default function DashboardPage() {
  const [stats, setStats] = useState({
    total: 0,
    accepted: 0,
    rejected: 0,
    rescued: 0,
    f1: 0,
    precision: 0,
    recall: 0
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isActive = true;

    async function fetchAnalytics() {
      try {
        const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const response = await fetch(`${baseUrl}/api/analytics`);
        if (!response.ok) throw new Error("Failed to fetch analytics");
        const data = await response.json();
        
        if (isActive && data.stats) {
          setStats(data.stats);
        }
      } catch (error) {
        console.error("Error fetching analytics:", error);
      } finally {
        if (isActive) setLoading(false);
      }
    }

    fetchAnalytics();
    
    // Auto-refresh every 5 seconds to pseudo-mimic live updates
    const intervalId = setInterval(fetchAnalytics, 5000);

    return () => {
      isActive = false;
      clearInterval(intervalId);
    };
  }, []);

  const MetricCard = ({ title, value, icon: Icon, colorClass, isPercentage = true }) => (
    <div className={styles.metricCard}>
      <div className={`${styles.metricBlur} ${colorClass}`}></div>
      <div className={styles.metricHeader}>
        <div className={`${styles.metricIconWrap} ${colorClass}`}>
          <Icon size={24} color="#fff" />
        </div>
      </div>
      <h3 className={styles.metricTitle}>{title}</h3>
      <p className={styles.metricValue}>
        {isPercentage ? `${(value * 100).toFixed(1)}%` : value}
      </p>
    </div>
  );

  return (
    <AuthGuard>
      <main className={styles.main}>
        <div className={styles.container}>
          <header className={styles.header}>
            <div className={styles.headerLeft}>
              <Link href="/cull" className={styles.backBtn}>
                <ArrowLeft size={24} />
              </Link>
              <h1 className={styles.title}>
                Intelligence Dashboard
              </h1>
            </div>
          </header>

          <div className={styles.metricsGrid}>
            <MetricCard title="System F1 Score" value={stats.f1} icon={Target} colorClass={styles.bgBlue} />
            <MetricCard title="Precision" value={stats.precision} icon={TrendingUp} colorClass={styles.bgGreen} />
            <MetricCard title="Recall" value={stats.recall} icon={BarChart3} colorClass={styles.bgPurple} />
            <MetricCard title="Rescued Photos" value={stats.rescued} icon={ShieldAlert} colorClass={styles.bgRed} isPercentage={false} />
          </div>

          <div className={styles.contentGrid}>
            {/* Performance Summary */}
            <section className={styles.sectionBox}>
              <h2 className={styles.sectionTitle}>
                <TrendingUp className={styles.textBlue} /> Accuracy Breakdown
              </h2>
              <div>
                <div className={styles.progressRow}>
                  <div className={styles.progressLabelWrap}>
                    <span className={styles.progressLabel}>Model Precision</span>
                    <span className={`${styles.progressValue} ${styles.textGreen}`}>{(stats.precision * 100).toFixed(1)}%</span>
                  </div>
                  <div className={styles.progressBarTrack}>
                    <motion.div 
                      initial={{ width: 0 }}
                      animate={{ width: `${stats.precision * 100}%` }}
                      className={`${styles.progressBarFill} ${styles.bgGreen} ${styles.shadowGreen}`}
                    />
                  </div>
                </div>

                <div className={styles.progressRow}>
                  <div className={styles.progressLabelWrap}>
                    <span className={styles.progressLabel}>Model Recall</span>
                    <span className={`${styles.progressValue} ${styles.textPurple}`}>{(stats.recall * 100).toFixed(1)}%</span>
                  </div>
                  <div className={styles.progressBarTrack}>
                    <motion.div 
                      initial={{ width: 0 }}
                      animate={{ width: `${stats.recall * 100}%` }}
                      className={`${styles.progressBarFill} ${styles.bgPurple} ${styles.shadowPurple}`}
                    />
                  </div>
                </div>

                <div className={styles.infoBox}>
                  <p className={styles.infoText}>
                    &quot;Higher F1 score indicates better balance between the model&apos;s ability to find good photos (Recall) and the reliability of those selections (Precision).&quot;
                  </p>
                </div>
              </div>
            </section>

            {/* Activity Logs */}
            <section className={styles.sectionBox}>
              <h2 className={styles.sectionTitle}>
                <BarChart3 className={styles.textPink} /> Quick Stats
              </h2>
              <div className={styles.statsGrid}>
                  <div className={styles.statItem}>
                      <p className={styles.statLabel}>Total Processed</p>
                      <p className={styles.statValue}>{stats.total}</p>
                  </div>
                  <div className={styles.statItem}>
                      <p className={styles.statLabel}>Approved</p>
                      <p className={`${styles.statValue} ${styles.textGreen}`}>{stats.accepted}</p>
                  </div>
                  <div className={styles.statItem}>
                      <p className={styles.statLabel}>Rejected</p>
                      <p className={`${styles.statValue} ${styles.textRed}`}>{stats.rejected}</p>
                  </div>
                  <div className={styles.statItem}>
                      <p className={styles.statLabel}>Waitlist</p>
                      <p className={`${styles.statValue} ${styles.textBlue}`}>{stats.total - stats.accepted - stats.rejected}</p>
                  </div>
              </div>
            </section>
          </div>
        </div>
      </main>
    </AuthGuard>
  );
}
