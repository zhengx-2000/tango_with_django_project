from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from rango.models import Category, Page, UserProfile
from rango.forms import CategoryForm, PageForm, UserForm, UserProfileForm
from datetime import datetime
from rango.bing_search import run_query
from django.views import View


def get_server_side_cookie(request, cookie, default_val=None):
    val = request.session.get(cookie)
    if not val:
        val = default_val
    return val


def visitor_cookie_handler(request):
    visits = int(get_server_side_cookie(request, 'visits', '1'))
    last_visit_cookie = get_server_side_cookie(request, 'last_visit', str(datetime.now()))
    last_visit_time = datetime.strptime(last_visit_cookie[:-7], '%Y-%m-%d %H:%M:%S')
    if (datetime.now() - last_visit_time).days > 0:
        visits = visits + 1
        request.session['last_visit'] = str(datetime.now())
    else:
        request.session['last_visit'] = last_visit_cookie
    request.session['visits'] = visits


class IndexView(View):
    def get(self, request):
        category_list = Category.objects.order_by('-likes')[:5]
        page_list = Page.objects.order_by('-views')[:5]

        context_dict = {}
        context_dict['boldmessage'] = 'Crunchy, creamy, cookie, candy, cupcake!'
        context_dict['categories'] = category_list
        context_dict['pages'] = page_list
        context_dict['extra'] = 'From the model solution on GitHub'

        visitor_cookie_handler(request)

        return render(request, 'rango/index.html', context=context_dict)


class AboutView(View):
    def get(self, request):
        context_dict = {}

        visitor_cookie_handler(request)
        context_dict['visits'] = request.session['visits']

        return render(request, 'rango/about.html', context_dict)


class ShowCategoryView(View):
    context_dict = {}

    def get(self, request, category_name_slug):

        try:
            category = Category.objects.get(slug=category_name_slug)
            pages = Page.objects.filter(category=category).order_by('-views')

            self.context_dict['pages'] = pages
            self.context_dict['category'] = category
        except Category.DoesNotExist:
            self.context_dict['pages'] = None
            self.context_dict['category'] = None

        return render(request, 'rango/category.html', context=self.context_dict)

    @method_decorator(login_required)
    def post(self, request, category_name_slug):
        query = request.POST['query'].strip()

        if query:
            self.context_dict['result_list'] = run_query(query)
            self.context_dict['query'] = query

        return render(request, 'rango/category.html', context=self.context_dict)


class AddCategoryView(View):
    @method_decorator(login_required)
    def get(self, request):
        form = CategoryForm()
        return render(request, 'rango/add_category.html', {'form': form})

    @method_decorator(login_required)
    def post(self, request):
        form = CategoryForm(request.POST)

        if form.is_valid():
            form.save(commit=True)
            return redirect(reverse('rango:index'))
        else:
            print(form.errors)

        return render(request, 'rango/add_category.html', {'form': form})


class AddPageView(View):
    form = PageForm()
    category = None

    @method_decorator(login_required)
    def get(self, request, category_name_slug):
        try:
            self.category = Category.objects.get(slug=category_name_slug)
        except:
            self.category = None

            # You cannot add a page to a Category that does not exist... DM
        if self.category is None:
            return redirect(reverse('rango:index'))

        context_dict = {'form': self.form, 'category': self.category}
        return render(request, 'rango/add_page.html', context=context_dict)

    @method_decorator(login_required)
    def post(self, request, category_name_slug):
        self.form = PageForm(request.POST)

        if self.form.is_valid():
            if self.category:
                page = self.form.save(commit=False)
                page.category = self.category
                page.views = 0
                page.save()

                return redirect(reverse('rango:show_category', kwargs={'category_name_slug': category_name_slug}))
        else:
            print(self.form.errors)  # This could be better done; for the purposes of TwD, this is fine. DM.

        context_dict = {'form': self.form, 'category': self.category}
        return render(request, 'rango/add_page.html', context=context_dict)


class RestrictedView(View):
    @method_decorator(login_required)
    def get(self, request):
        return render(request, 'rango/restricted.html')


class GotoUrlView(View):
    def get(self, request):
        page_id = request.GET.get('page_id')

        try:
            selected_page = Page.objects.get(id=page_id)
        except Page.DoesNotExist:
            return redirect(reverse('rango:index'))

        selected_page.views = selected_page.views + 1
        selected_page.save()

        return redirect(selected_page.url)

    def post(self, request):
        return redirect(reverse('rango:index'))


class RegisterProfileView(View):
    form = UserProfileForm()

    @method_decorator(login_required)
    def get(self, request):
        context_dict = {'form': self.form}
        return render(request, 'rango/profile_registration.html', context_dict)

    @method_decorator(login_required)
    def post(self, request):
        self.form = UserProfileForm(request.POST, request.FILES)

        if self.form.is_valid():
            user_profile = self.form.save(commit=False)
            user_profile.user = request.user
            user_profile.save()

            return redirect(reverse('rango:index'))
        else:
            print(self.form.errors)

        context_dict = {'form': self.form}
        return render(request, 'rango/profile_registration.html', context_dict)


class ProfileView(View):
    def get_user_details(self, username):
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return None

        user_profile = UserProfile.objects.get_or_create(user=user)[0]
        form = UserProfileForm({'website': user_profile.website,
                                'picture': user_profile.picture})

        return (user, user_profile, form)

    @method_decorator(login_required)
    def get(self, request, username):
        try:
            (user, user_profile, form) = self.get_user_details(username)
        except TypeError:
            return redirect(reverse('rango:index'))

        context_dict = {'user_profile': user_profile,
                        'selected_user': user,
                        'form': form}

        return render(request, 'rango/profile.html', context_dict)

    @method_decorator(login_required)
    def post(self, request, username):
        try:
            (user, user_profile, form) = self.get_user_details(username)
        except TypeError:
            return redirect(reverse('rango:index'))

        form = UserProfileForm(request.POST, request.FILES, instance=user_profile)
        if form.is_valid():
            form.save(commit=True)
            return redirect('rango:profile', user.username)
        else:
            print(form.errors)

        context_dict = {'user_profile': user_profile,
                        'selected_user': user,
                        'form': form}

        return render(request, 'rango/profile.html', context_dict)


class ListProfilesView(View):
    @method_decorator(login_required)
    def get(self, request):
        profiles = UserProfile.objects.all()

        return render(request, 'rango/list_profiles.html', {'userprofile_list': profiles})
