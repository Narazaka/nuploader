#!/usr/bin/perl
use utf8;
use lib 'local/lib';
use Mojolicious::Lite;
use Config::Column;
use Digest::SHA 'sha256_hex';
use File::Spec::Functions 'catfile';
use File::MMagic;
use Encode;
#binmode STDERR, ':encoding(cp932)';
#binmode STDOUT, ':encoding(cp932)';

plugin 'Config', file => '.uploader.conf';

$ENV{MOJO_MAX_MESSAGE_SIZE} = app->config->{max_message_size};

my $mm = File::MMagic->new();
my $cc = Config::Column->new(
	app->config->{list_file},
	'utf8',
	[qw(filename view_password_sha256_hex delete_password_sha256_hex description)],
	"\t",
);

sub find_item{
	my ($list, $filename) = @_;
	$filename = Encode::decode('utf8', $filename); # for core server
	my $use_item;
	my $use_index;
	for my $i (0 .. $#$list){
		my $item = $list->[$i];
		if($item->{filename} eq $filename){
			$use_item = $item;
			$use_index = $i;
			last;
		}
	}
	return wantarray ? ($use_item, $use_index) : $use_item;
}

get '/' => sub {
	my $self = shift;
	my $list = $cc->read_data || [];
	$self->render('index', title => $self->config->{title}, list => $list);
} => 'index';

post '/upload' => sub {
	my $self = shift;
	if($self->req->is_limit_exceeded){
		$self->flash(error => 'サイズが大きすぎます。' . sprintf('%.1f', $ENV{MOJO_MAX_MESSAGE_SIZE} / (1024 ** 2)) . 'MBまでです。');
		return $self->redirect_to('index');
	}
	my $view_password = $self->param('view_password');
	my $delete_password = $self->param('delete_password');
	my $view_password_sha256_hex = length $view_password ? sha256_hex $view_password : '';
	my $delete_password_sha256_hex = length $delete_password ? sha256_hex $delete_password : '';
	my $description = $self->param('description');
	$description =~ s/[\t\n\r]/ /g;
	my $file = $self->param('file');
	unless($file and $file->size){
		$self->flash(error => 'ファイルを指定してください。');
		return $self->redirect_to('index');
	}
	my $filename = $file->filename;
	$filename =~ s@[/\t\n\r]@_@g;
	my $index = $cc->read_data_num;
	my $use_filename = ($index + 1) . '_' . $filename;
	my $filepath = catfile $self->config->{files_place}, $use_filename;
	$file->move_to($filepath);
	$cc->add_data({filename => $use_filename, view_password_sha256_hex => $view_password_sha256_hex, delete_password_sha256_hex => $delete_password_sha256_hex, description => $description});
	$self->flash(info => $use_filename . 'をアップロードしました。');
	$self->redirect_to('index');
};

get '/file/*filename' => sub {
	my $self = shift;
	my $filename = $self->param('filename');
	my $list = $cc->read_data || [];
	my $use_item = find_item($list, $filename);
	unless($use_item){
		return $self->render_not_found;
	}
	if(length $use_item->{view_password_sha256_hex} and $use_item->{view_password_sha256_hex} ne sha256_hex $self->param('view_password')){
		$self->flash(error => 'パスワードが違います。');
		return $self->redirect_to('index');
	}
	my $filepath = catfile $self->config->{files_place}, $use_item->{filename};
	my $file = Mojo::Asset::File->new(path => $filepath);
	$self->res->headers->content_type($mm->checktype_contents($file->get_chunk()) . '; charset=UTF-8');
#	$self->res->headers->content_disposition(qq/attachment; filename="$filename"/);
	$self->res->headers->content_disposition(qq/attachment/);
	if($file->size < $self->config->{non_chunk_size_limit}){
		$self->render(data => $file->slurp);
	}else{
		my $pos = 0;
		my $drain;
		$drain = sub{
			my $content = shift;
			my $chunk = $file->get_chunk($pos);
			my $chunk_length = length $chunk;
			$pos += $chunk_length;
			$drain = undef unless $chunk_length;
			$content->write_chunk($chunk, $drain);
		};
		$self->$drain;
	}
};

get '/delete/*filename' => sub {
	my $self = shift;
	my $filename = $self->param('filename');
	my $list = $cc->read_data || [];
	my ($use_item, $use_index) = find_item($list, $filename);
	unless($use_item){
		return $self->render_not_found;
	}
	my $delete_password_sha256_hex = sha256_hex $self->param('delete_password');
	if($use_item->{delete_password_sha256_hex} ne $delete_password_sha256_hex and $self->config->{admin_delete_password_sha256hex} ne $delete_password_sha256_hex){
		$self->flash(error => 'パスワードが違います。');
		return $self->redirect_to('index');
	}
	my $filepath = catfile $self->config->{files_place}, $use_item->{filename};
	unlink $filepath;
	$list->[$use_index] = {};
	$cc->write_data($list);
	$self->flash(info => $use_item->{filename} . 'を削除しました。');
	$self->redirect_to('index');
};

app->start;
