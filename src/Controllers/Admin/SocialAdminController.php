<?php

namespace Cauri\Controllers\Admin;

use Cauri\Core\Config;
use Cauri\Core\HttpException;
use Cauri\Core\Request;
use Cauri\Core\Response;
use Cauri\Services\AI\AiFactory;
use Cauri\Services\Audit;
use Cauri\Services\Social\PostGenerator;

/** Posts réseaux sociaux : aperçu, légende à copier, statut (publié, écarté) et génération à la demande. */
final class SocialAdminController extends BaseAdminController
{
    public const THEMES = ['classement', 'artiste', 'weekend'];

    public function index(Request $request): Response
    {
        $this->requireUser($request);
        $posts = $this->db->all('SELECT * FROM social_posts ORDER BY slot_date DESC, FIELD(theme, \'classement\', \'artiste\', \'weekend\') LIMIT 45');
        foreach ($posts as &$p) {
            $p['slides'] = array_map(fn ($s) => is_array($s) ? $s : ['file' => $s, 'label' => ''], json_decode((string) ($p['carousel'] ?? '[]'), true) ?: []);
        }
        unset($p);
        return $this->admin('posts', ['posts' => $posts, 'exportDir' => \Cauri\Core\Env::get('SOCIAL_EXPORT_DIR')]);
    }

    /** Génère (ou régénère) un post ou les trois, datés d'aujourd'hui. */
    public function generate(Request $request): Response
    {
        $this->requireUser($request);
        $theme = $request->str('theme');
        $themes = $theme === 'tous' ? self::THEMES : (in_array($theme, self::THEMES, true) ? [$theme] : []);
        if (!$themes) {
            throw new HttpException(400);
        }
        @set_time_limit(600); // texte IA, visuels et vidéo : jusqu'à une minute par post
        $generator = new PostGenerator($this->db, AiFactory::make());
        $done = [];
        foreach ($themes as $t) {
            if ($post = $generator->generate($t)) {
                $done[] = $post['title'];
            }
        }
        Audit::log($this->uid(), 'social.generate', 'social_post', null, implode(', ', $themes), ['titles' => $done], $request->ip());
        return $this->back(path('admin/posts'), $done ? 'success' : 'error', $done ? t('admin.posts_generated', ['n' => count($done)]) : t('admin.posts_no_data'));
    }

    public function status(Request $request): Response
    {
        $this->requireUser($request);
        $id = (int) $request->param('id');
        $status = $request->str('status');
        if (!in_array($status, ['draft', 'approved', 'published', 'rejected'], true) || !$this->db->value('SELECT 1 FROM social_posts WHERE id = ?', [$id])) {
            throw new HttpException(400);
        }
        $this->db->update('social_posts', ['status' => $status], 'id = :id', ['id' => $id]);
        Audit::log($this->uid(), 'social.status', 'social_post', $id, $status, [], $request->ip());
        return $this->back(path('admin/posts') . '#post-' . $id, 'success', t('admin.saved'));
    }
}
