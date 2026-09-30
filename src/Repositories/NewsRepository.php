<?php

namespace Cauri\Repositories;

use Cauri\Core\Database;

final class NewsRepository
{
    public const CATEGORIES = ['annonce', 'classement', 'sortie', 'evenement', 'industrie'];

    public function __construct(private Database $db)
    {
    }

    /** Actualités publiées : celles du pays et celles qui concernent tous les pays. */
    public function latest(int $limit = 5, ?int $countryId = null, int $offset = 0): array
    {
        $params = [gmdate('Y-m-d H:i:s')];
        $where = "n.status = 'published' AND n.published_at <= ?";
        if ($countryId) {
            $where .= ' AND (n.country_id IS NULL OR n.country_id = ?)';
            $params[] = $countryId;
        }
        return $this->db->all(
            "SELECT n.*, c.code AS country_code FROM news n LEFT JOIN countries c ON c.id = n.country_id
             WHERE $where ORDER BY n.published_at DESC LIMIT " . (int) $limit . ' OFFSET ' . (int) $offset,
            $params
        );
    }

    public function countPublished(): int
    {
        return (int) $this->db->value("SELECT COUNT(*) FROM news WHERE status = 'published' AND published_at <= ?", [gmdate('Y-m-d H:i:s')]);
    }

    public function bySlug(string $slug): ?array
    {
        return $this->db->one(
            "SELECT n.*, c.code AS country_code FROM news n LEFT JOIN countries c ON c.id = n.country_id
             WHERE n.slug = ? AND n.status = 'published' AND n.published_at <= ?",
            [$slug, gmdate('Y-m-d H:i:s')]
        );
    }
}
